import torch
import torch.nn as nn
import tiktoken
from torch.nn import functional as F
import config

class MultiHeadAttention(nn.Module):
    def __init__(self, num_heads, head_size):
        super().__init__()
        self.num_heads = num_heads
        self.head_size = head_size
        
        self.key = nn.Linear(config.n_embd, num_heads * head_size, bias=False)
        self.query = nn.Linear(config.n_embd, num_heads * head_size, bias=False)
        self.value = nn.Linear(config.n_embd, num_heads * head_size, bias=False)
        self.proj = nn.Linear(num_heads * head_size, config.n_embd)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        B, T, C = x.size()
        
        # Linear transformation and split into multiple heads
        k = self.key(x).view(B, T, self.num_heads, self.head_size)
        q = self.query(x).view(B, T, self.num_heads, self.head_size)
        v = self.value(x).view(B, T, self.num_heads, self.head_size)

        # Transpose to prepare for matrix multiplication
        k = k.transpose(1, 2)  # (B, num_heads, T, head_size)
        q = q.transpose(1, 2)  # (B, num_heads, T, head_size)
        v = v.transpose(1, 2)  # (B, num_heads, T, head_size)

        # Compute attention scores
        attention_scores = torch.matmul(q, k.transpose(-2, -1)) / (self.head_size ** 0.5)  # (B, num_heads, T, T)

        # Mask out upper triangular elements
        mask = torch.tril(torch.ones(T, T, device=x.device)).unsqueeze(0)  # (1, T, T)
        attention_scores = attention_scores.masked_fill(mask == 0, float('-inf'))

        # Apply softmax and dropout
        attention_weights = F.softmax(attention_scores, dim=-1)
        attention_weights = self.dropout(attention_weights)

        # Weighted sum of values
        out = torch.matmul(attention_weights, v)  # (B, num_heads, T, head_size)

        # Transpose and concatenate heads
        out = out.transpose(1, 2).contiguous().view(B, T, -1)  # (B, T, num_heads * head_size)

        # Project back to the original dimension
        out = self.proj(out)

        return out

class MLP(nn.Module):
    def __init__(self, n_embd):
        super().__init__()
        self.linear = nn.Linear(n_embd, 4 * n_embd)
        self.activation = nn.GELU()
        self.proj = nn.Linear(4 * n_embd, n_embd)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        x = self.linear(x)
        x = self.activation(x)
        x = self.proj(x)
        x = self.dropout(x)
        return x

class Block(nn.Module):
    
    def __init__(self, n_embd, n_head):
        # n_embd: embedding dimension, n_head: the number of heads we'd like
        super().__init__()
        head_size = n_embd // n_head
        self.sa = MultiHeadAttention(n_head, head_size)
        self.mlp = MLP(n_embd)
        self.ln1 = nn.LayerNorm(n_embd)
        self.ln2 = nn.LayerNorm(n_embd)

    def forward(self, x):
        x = x + self.sa(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x

class GPTLanguageModel(nn.Module):

    def __init__(self):
        super().__init__()
        # each token directly reads off the logits for the next token from a lookup table (gets probability for next token)
        self.token_embedding_table = nn.Embedding(config.vocab_size, config.n_embd)
        self.position_embedding_table = nn.Embedding(config.block_size, config.n_embd)
        self.blocks = nn.Sequential(*[Block(config.n_embd, config.n_head) for _ in range(config.n_layer)])
        self.ln_f = nn.LayerNorm(config.n_embd) # final layer norm
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size)
        self.apply(self._init_weights)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def num_parameters(self):
        num_params = sum(p.numel() for p in self.parameters()) / 1e6
        return num_params

    def forward(self, idx, targets=None):
        B, T = idx.shape

        # idx and targets are both (B,T) tensor of integers
        tok_emb = self.token_embedding_table(idx) # (B,T,C)
        pos_emb = self.position_embedding_table(torch.arange(T, device=config.device)) # (T,C)
        x = tok_emb + pos_emb # (B,T,C)
        x = self.blocks(x) # (B,T,C)
        x = self.ln_f(x) # (B,T,C)
        logits = self.lm_head(x) # (B,T,vocab_size)

        if targets is None:
            loss = None
        else:
            B, T, C = logits.shape
            logits = logits.view(B*T, C)
            targets = targets.view(B*T)
            loss = F.cross_entropy(logits, targets)

        return logits, loss
    
    @torch.no_grad()
    def generate(self, prompt, max_new_tokens, temperature, batch_size=10):
        self.eval()
        enc = tiktoken.get_encoding("gpt2")
        prompt_tokens = enc.encode(prompt)
        idx = torch.tensor([prompt_tokens], dtype=torch.long, device=self.token_embedding_table.weight.device)

        generated_tokens = []

        while len(generated_tokens) < max_new_tokens:
            batch_tokens = []
            for _ in range(batch_size):
                idx_cond = idx[:, -config.block_size:] # Crop context to last block_size tokens
                logits, _ = self(idx_cond) # Get logits for next token
                logits = logits[:, -1, :] / temperature
                probs = F.softmax(logits, dim=-1) # Calculate probabilities
                idx_next = torch.multinomial(probs, num_samples=1)
                batch_tokens.append(idx_next.squeeze().tolist())

            idx_next_batch = torch.tensor(batch_tokens, dtype=torch.long, device=idx.device).unsqueeze(0)
            idx = torch.cat((idx, idx_next_batch), dim=1)
            generated_tokens.extend(batch_tokens)

        result = enc.decode(generated_tokens)
        return result