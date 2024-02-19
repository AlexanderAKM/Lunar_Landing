import gymnasium as gym
import math 
import random
#import matplotlib
#import matplotlib.pyplot as plt
import pandas as pd
from collections import namedtuple, deque

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F

def run(episodes):

    env = gym.make("LunarLander-v2")

    # If you're using Jupyter Notebook, uncomment the imports and the following lines:
    # is_ipython = 'inline' in matplotlib.get_backend():
    # if is_ipython:
        # from IPython import display

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    Transition = namedtuple('Transition',
                            ('state', 'action', 'next_state', 'reward'))

    class ReplayMemory(object):
        def __init__(self, capacity):
            self.memory = deque([], maxlen = capacity)

        def push(self, *args):
            self.memory.append(Transition(*args))

        def sample(self, batch_size):
            return random.sample(self.memory, batch_size)
        
        def __len__(self):
            return len(self.memory)
        
    class DQN(nn.Module):
        def __init__(self, n_observations, n_actions):
            super(DQN, self).__init__()
            self.layer1 = nn.Linear(n_observations, 128)
            self.layer2 = nn.Linear(128, 128)
            self.layer3 = nn.Linear(128, n_actions)

        def forward(self, x):
            x = F.relu(self.layer1(x))
            x = F.relu(self.layer2(x))
            return self.layer3(x)
        
    BATCH_SIZE = 128
    GAMMA = 0.995
    EPS_START = 0.9
    EPS_END = 0.05
    EPS_DECAY = 1000
    TAU = 0.005
    LR = 1e-4

    n_actions = env.action_space.n

    state, info = env.reset()
    n_observations = len(state)

    policy_net = DQN(n_observations, n_actions).to(device)
    target_net = DQN(n_observations, n_actions).to(device)
    target_net.load_state_dict(policy_net.state_dict())

    optimizer = optim.AdamW(policy_net.parameters(), lr=LR, amsgrad=True)
    memory = ReplayMemory(10000)

    steps_done = 0

    def select_action(state):
        nonlocal steps_done
        sample = random.random()
        eps_threshold = EPS_END + (EPS_START - EPS_END) * math.exp(-1 * steps_done / EPS_DECAY)
        steps_done += 1

        if sample > eps_threshold:
            with torch.no_grad():
                return policy_net(state).max(1).indices.view(1,1)
        else:
            return torch.tensor([[env.action_space.sample()]],
                                device = device, dtype = torch.long)
        
    episode_durations = []
    rewards_episodes = {'Episode': [], 'Reward': []}

    def optimize_model():
        transitions = memory.sample(BATCH_SIZE)
        batch = Transition(*zip(*transitions))

        non_final_mask = torch.tensor(tuple(map(lambda s: s is not None,
                                                batch.next_state)),
                                                device = device, dtype = torch.bool)
        non_final_next_states = torch.cat([s for s in batch.next_state if s is not None])

        state_batch = torch.cat(batch.state)
        action_batch = torch.cat(batch.action)
        reward_batch = torch.cat(batch.reward)

        state_action_values = policy_net(state_batch).gather(1, action_batch)
        next_state_values = torch.zeros(BATCH_SIZE, device = device)

        with torch.no_grad():
            next_state_actions = policy_net(non_final_next_states).max(1, keepdim=True)[1]
            next_state_values[non_final_mask] = target_net(non_final_next_states).gather(1, next_state_actions).squeeze()

        expected_state_action_values = (next_state_values * GAMMA) + reward_batch

        criterion = nn.SmoothL1Loss()
        loss = criterion(state_action_values, expected_state_action_values.unsqueeze(1))

        optimizer.zero_grad()
        loss.backward()
        for param in policy_net.parameters():
            param.grad.data.clamp(-1, 1)
        optimizer.step()

    for episode in range(episodes):
        if episode % 50 == 0:
            print(f"episode: {episode}")
        state, info = env.reset()
        state = torch.tensor(state, dtype = torch.float32, device = device).unsqueeze(0)
        total_reward = 0
        terminated, truncated = False, False

        while not terminated and not truncated:
            action = select_action(state)
            observation, reward, terminated, truncated, _ = env.step(action.item())

            total_reward += reward
            reward = torch.tensor([reward], device = device)

            if terminated:
                next_state = None
            else:
                next_state = torch.tensor(observation, dtype=torch.float32, device=device).unsqueeze(0)

            memory.push(state, action, next_state, reward)
            state = next_state

            if len(memory) > BATCH_SIZE:
                optimize_model()

            target_net_state_dict = target_net.state_dict()
            policy_net_state_dict = policy_net.state_dict()
            for key in policy_net_state_dict:
                target_net_state_dict[key] = policy_net_state_dict[key] * TAU + target_net_state_dict[key] * (1-TAU)
                target_net.load_state_dict(target_net_state_dict)
        
        rewards_episodes['Episode'].append(episode)
        rewards_episodes['Reward'].append(total_reward)
    rewards_file_path = f'data/input/rewards_double_dqn_{episodes}.csv'
    df_rewards = pd.DataFrame(rewards_episodes)
    df_rewards.to_csv(rewards_file_path, index=False)

    env.close()

run(500)      




