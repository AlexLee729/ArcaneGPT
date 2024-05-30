# 123.69M Model
import torch

# Model Hyperparameters
batch_size = 4  # Number of sequences run in parallel
block_size = 1024  # Context size used for prediction
n_embd = 768
n_head = 12
n_layer = 12
dropout = 0.0
vocab_size = 50304  # GPT-2 vocabulary size
beta1 = 0.9
beta2 = 0.95
bias = True
decay_lr = True

# Training Hyperparameters
max_iters = 30000
lr_decay_iters = 30000
warmup_iters = 100
gradient_accumulation_steps = 2

eval_interval = 1000
learning_rate = 6e-4
weight_decay = 1e-1
min_lr = 6e-5
eval_iters = 200

# Finetuning Hyperparameters
# max_iters = 40
# eval_interval = 5
# learning_rate = 3e-5
# eval_iters = 200

# Macbook GPU
#device = 'mps' if torch.backends.mps.is_available() else 'cpu'

device = 'cuda'