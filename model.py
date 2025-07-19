import torch.optim as optim
import torch.nn as nn
import torch_directml
import torch
from pathlib import Path

class GDAI(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv_block_1 = nn.Sequential(
            nn.Conv2d(in_channels=1, 
                      out_channels=16, 
                      kernel_size=3, # how big is the square that's going over the image?
                      stride=1, # default
                      padding=1), # options = "valid" (no padding) or "same" (output has same shape as input) or int for specific number 
            nn.ReLU(),
            nn.Conv2d(in_channels=16, 
                      out_channels=64,
                      kernel_size=3,
                      stride=1,
                      padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        self.conv_block_2 = nn.Sequential(
            nn.Conv2d(64, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, 8, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )

        self.classifier = nn.Sequential(
            nn.Flatten(),
            # Where did this in_features shape come from? 
            # It's because each layer of our network compresses and changes the shape of our input data.
            nn.Linear(in_features=3528, out_features=1) # Adjusted for 84x84 input
        )
    
    def forward(self, x: torch.Tensor):
        x = self.conv_block_1(x)
        x = self.conv_block_2(x)
        x = self.classifier(x)
        # Return raw Q-values, not the argmax or one-hot encoding
        return x
    
    def save(self, file_name='model.pth'):
        model_folder_path = Path('model')
        model_folder_path.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists
        file_name = model_folder_path / file_name
        torch.save(self.state_dict(), file_name)

    def load(self, file_name='model.pth'):
        model_folder_path = Path('model')
        if not model_folder_path.exists():
            print("No Model Folder")
            return
        file_name = model_folder_path / file_name
        self.load_state_dict(torch.load(f=file_name))

class Trainer:
    def __init__(self, model, lr, gamma):
        self.lr = lr
        self.gamma = gamma
        self.device = torch_directml.device()
        
        self.model = model
        self.optimizer = optim.Adam(model.parameters(), lr=self.lr)
        self.criterion = nn.MSELoss()

    def train_step(self, state, action, reward, next_state, done):
        # Convert to tensors and move to device
        if not isinstance(state, torch.Tensor):
            state = torch.stack(state, dim=0).float().to(self.device).requires_grad_(True)
            action = torch.stack(action, dim=0).float().to(self.device)
            reward = torch.tensor(reward, dtype=torch.float).to(self.device)
            next_state = torch.stack(next_state, dim=0).float().to(self.device)
            done = torch.tensor(done, dtype=torch.bool).to(self.device)
        else:
            state = state.unsqueeze(0).float().to(self.device).requires_grad_(True)
            action = action.unsqueeze(0).float().to(self.device)
            reward = torch.tensor(reward, dtype=torch.float).unsqueeze(0).to(self.device)
            next_state = next_state.unsqueeze(0).float().to(self.device)
            done = torch.tensor(done, dtype=torch.bool).unsqueeze(0).to(self.device)

        self.model.train()  # Ensure the model is in training mode

        # Predicted Q values with current state
        pred = self.model(state)

        # Calculate target Q-values
        with torch.no_grad(): # Ensure target calculation does not track gradients
            next_Q_values = self.model(next_state)
            max_next_Q = torch.max(next_Q_values, dim=1)[0]
            
            # Bellman equation: Q_target = reward + gamma * max_Q(next_state)
            # For terminal states (done=True), Q_target is just the reward
            target_Q_values = reward + self.gamma * max_next_Q * (~done)
            
            # Unsqueeze to match pred's shape (batch_size, 1)
            target_Q_values = target_Q_values.unsqueeze(1)

        self.optimizer.zero_grad()
        loss = self.criterion(pred, target_Q_values) # pred is the one requiring grad
        loss.backward()
        self.optimizer.step()