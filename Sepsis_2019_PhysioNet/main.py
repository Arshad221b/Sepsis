#!/usr/bin/env python

import numpy as np
import os, sys
import time
import argparse
import torch
import torch.nn as nn
from torch.nn import functional as F
from torch.autograd import Variable
from torch import optim
import math
from model import lstm
from pytorch_data_loader import Dataset
from driver import save_challenge_predictions
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader

#TODO: add more args, including train, etc.
parser = argparse.ArgumentParser(description='PyTorch Example')
parser.add_argument('--disable-cuda', action='store_true',
                    help='Disable CUDA')
args = parser.parse_args()
args.device = None
if not args.disable_cuda and torch.cuda.is_available() and False: #remove false
    args.device = torch.device('cuda')
    torch.set_default_tensor_type('torch.cuda.DoubleTensor')
else:
    args.device = torch.device('cpu')
    torch.set_default_tensor_type('torch.DoubleTensor')

def sort_by_seq_len(labels, pad_val=-1):
    '''
    returns descending order of array lengths ignoring pad_val entries
    '''
    seq_len = np.array([])
    for l in labels:
        arr = l.data.numpy()
        unique, counts = np.unique(arr, return_counts=True)
        counts = dict(zip(unique, counts))
        try: # will fail on max_len sequence since no -1 dict entries
            seq_len = np.append(seq_len, labels.shape[1] - counts[pad_val])
        except: seq_len = np.append(seq_len, len(l.data))
    # sort by sequence lengths
    order = torch.from_numpy(np.argsort(seq_len*-1))
    seq_len = torch.from_numpy(seq_len[order])
    return order, seq_len


partition = dict([])
partition['train'] = list(range(150))
partition['validation'] = list(range(150,200))

epochs = 30
embedding = 40
hidden_size = 64
num_layers = 2
batch_size = 4
save_rate = 10

train_data = Dataset(partition['train'])
train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)

val_data = Dataset(partition['validation'])
val_loader = DataLoader(val_data, batch_size=batch_size, shuffle=True)

ratio = 10 # TODO: manually find ratio of sepsis occurence

model = lstm(embedding, hidden_size, num_layers, batch_size, args.device)
#model.load_state_dict(torch.load('/home/wanglab/Osvald/Sepsis/Models/lstm40_2_64/model_epoch4_A'))
#model.eval()

criterion = nn.BCEWithLogitsLoss(pos_weight=torch.DoubleTensor([ratio]).to(args.device))
optimizer = optim.SGD(model.parameters(), lr=0.001)

train_losses = np.zeros(epochs)
val_losses = np.zeros(epochs)
# train accuracy
train_pos_acc = np.zeros(epochs)
train_neg_acc = np.zeros(epochs)
# val accuracy
val_pos_acc = np.zeros(epochs)
val_neg_acc = np.zeros(epochs)


# TODO: Figure out batching with different sizes w/o excessive padding
start = time.time()
for epoch in range(epochs):
    # Training
    running_loss = 0
    pos_total, pos_correct = 0, 0
    neg_total, neg_correct = 0, 0
    for batch, labels in train_loader:
        # pass to GPU if available
        batch, labels = batch.to(args.device), labels.to(args.device)
        max_len = labels.shape[1]
        if labels.shape[0] != 1:
            order, seq_len = sort_by_seq_len(labels) #TODO: Fix this inefficient method of counting sequence lengths -> move to data loader (in val loop too)            
            labels = labels[order, :]
            batch = batch[order, :]
        else: # if final batch is size 1
            seq_len = torch.Tensor([max_len])

        optimizer.zero_grad()
        outputs = model(batch, seq_len, max_len, batch_size)
        outputs = outputs.view(-1, max_len)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        running_loss += loss.data.numpy()/seq_len.sum().numpy()
    
        
        # Train Accuracy
        for i in range(labels.shape[0]):
            targets = labels.data[i,:int(seq_len[i])].numpy()
            predictions = torch.round(torch.sigmoid(outputs.data[i, :int(seq_len[i])])).numpy()
            match = targets == predictions
            pos_total += targets.sum()
            neg_total += (targets == 0).sum()
            pos_correct += (match * targets).sum()
            neg_correct += (match * (targets == 0)).sum()

    train_losses[epoch] = running_loss/len(train_loader)
    train_pos_acc[epoch] = pos_correct/pos_total
    train_neg_acc[epoch] = neg_correct/neg_total

    # Validation
    running_loss = 0
    pos_total, pos_correct = 0, 0
    neg_total, neg_correct = 0, 0
    with torch.set_grad_enabled(False):
        for batch, labels in val_loader:
            # pass to GPU if available
            batch, labels = batch.to(args.device), labels.to(args.device)
            max_len = labels.shape[1]
            if labels.shape[0] != 1:  
                order, seq_len = sort_by_seq_len(labels)  
                labels = labels[order, :]
                batch = batch[order, :]
            else: # if final batch is size 1
                seq_len = torch.Tensor([max_len])

            outputs = model(batch, seq_len, max_len, batch_size)
            outputs = outputs.view(-1, max_len)
            loss = criterion(outputs, labels)
            running_loss += loss.data.numpy()/seq_len.sum().numpy()
            
            # Validation Accuracy
            for i in range(labels.shape[0]):
                targets = labels.data[i,:int(seq_len[i])].numpy()
                predictions = torch.round(torch.sigmoid(outputs.data[i, :int(seq_len[i])])).numpy()
                match = targets == predictions
                pos_total += targets.sum()
                neg_total += (targets == 0).sum()
                pos_correct += (match * targets).sum()
                neg_correct += (match * (targets == 0)).sum()

        val_losses[epoch] = running_loss/len(val_loader)
        val_pos_acc[epoch] = pos_correct/pos_total
        val_neg_acc[epoch] = neg_correct/neg_total

    print('Epoch', epoch+1, 'train avg loss:', train_losses[epoch], 'validation avg loss:', val_losses[epoch])
    print('Epoch', epoch+1, 'train pos acc:', train_pos_acc[epoch], 'validation pos acc:', val_pos_acc[epoch])
    print('Epoch', epoch+1, 'train neg acc:', train_neg_acc[epoch], 'validation neg acc:', val_neg_acc[epoch])
    print('total runtime:', str(round(time.time() - start, 2)))

    #np.save('C:/Users/Osvald/Sepsis_ML/Models/lstm_batch/', train_losses)
    #np.save('C:/Users/Osvald/Sepsis_ML/Models/lstm_batch/', val_losses)
    #if (epoch+1) % save_rate ==0:
    #   torch.save(model.state_dict(), 'C:/Users/Osvald/Sepsis_ML/Models/lstm_batch/model_epoch%s' % (epoch+1))
        
    #np.save('/home/wanglab/Osvald/Sepsis/Models/lstm40_2_64/losses', losses)
    #if (epoch+1) % save_rate ==0:
    #   torch.save(model.state_dict(), '/home/wanglab/Osvald/Sepsis/Models/lstm40_2_64/model_epoch%s_A' % (epoch+1))
    
plt.plot(train_losses)
plt.plot(val_losses)
plt.show()
plt.plot(train_pos_acc)
plt.plot(train_neg_acc)
plt.plot(val_pos_acc)
plt.plot(val_neg_acc)
plt.show()