from torchvision import transforms
from collections import deque
from game import GeometryDash
from model import GDAI, Trainer
import torch_directml
import torch
import random
import time

MAX_MEMORY = 10000 # Increased memory for more diverse experiences
BATCH_SIZE = 256 # Larger batch size for more stable gradients
LR = 0.0005 # Slightly reduced learning rate for stability

class Player():
    def __init__(self):
        self.n_games = 0
        self.gamma = 0.9
        self.device = torch_directml.device()

        self.memory = deque(maxlen=MAX_MEMORY)
        self.model = GDAI()
        self.model.train()  # Set model to training mode
        
        self.trainer = Trainer(self.model, lr=LR, gamma=self.gamma)

        self.transform = transforms.Compose([
            transforms.ToPILImage(),  # Convert to PIL Image
            transforms.Resize((84, 84)), # Smaller resolution for faster processing
            transforms.Grayscale(num_output_channels=1), # (128, 128)
            transforms.ToTensor()
        ])

    def get_state(self, game: GeometryDash):
        frame = game.get_current_frame()
        transformed_frame = self.transform(frame)
        return transformed_frame
    
    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    def train_long_memory(self):
        if len(self.memory) > BATCH_SIZE: mini_sample = random.sample(self.memory, BATCH_SIZE) 
        else: mini_sample = self.memory

        states, actions, rewards, next_states, dones = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, dones)

    def train_short_memory(self, state, action, reward, next_state, done):
        self.trainer.train_step(state, action, reward, next_state, done)

    def get_action(self, state):
        if random.randint(0, 200) < 200 - self.n_games: # Reduced range for faster decay
            final_move = torch.tensor([random.randint(0, 1)])
        else:
            state = state.to(self.device)
            self.model.eval()  # Set model to evaluation mode
            
            with torch.no_grad(): # No need to calculate gradients for inference
                prediction = self.model(state.unsqueeze(0))
            
            final_move = torch.round(prediction).squeeze(0)
            
            final_move = final_move.to(torch.device('cpu')).detach()  # Move back to CPU
        return final_move

def main():
    record = 0
    
    player = Player()
    game = GeometryDash()
    
    time.sleep(1)
    player.model.load()
    game.start_game()
    while True:
        state_old = player.get_state(game)
        final_move = player.get_action(state_old)

        reward, done, score = game.read_input(final_move)
        state_new = player.get_state(game)

        # train short memory
        player.train_short_memory(state_old, final_move, reward, state_new, done)
        player.remember(state_old, final_move, reward, state_new, done)

        if done:
            player.n_games += 1
            player.train_long_memory()

            if score > record:
                record = score
                player.model.save()

            print('Game', player.n_games, 'Score', score, 'Record:', record)
            
            # Starting Next Game
            game.reset_inputs()
            game.reset_timer()
            game.start_game()


if __name__ == '__main__':
    main()