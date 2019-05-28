#!/usr/bin/env python

import numpy as np
import torch
from torch.utils import data
import os, sys
from driver import save_challenge_predictions

#raw_dir = "D:/Sepsis Challenge/training"
#pth = 'C:/Users/Osvald/Sepsis_ML/'
raw_dir = '/home/osvald/Projects/Diagnostics/CinC_data/training'
pth = '/home/osvald/Projects/Diagnostics/CinC_data/tensors/'

def load_challenge_data(file, split=True):
    with open(file, 'r') as f:
        header = f.readline().strip()
        column_names = header.split('|')
        data = np.loadtxt(f, delimiter='|')
    
    if column_names[-1] != 'SepsisLabel':
        print(file, ' does not have sepsis label')
        return
    elif split:
        labels = data[:, -1]
        column_names = column_names[:-1]
        data = data[:, :-1]
    else:
        data, labels = data, None
    
    return data, labels

def load_data(input_directory, limit=100, split=True):

    # Find files.
    files = []
    for f in os.listdir(input_directory):
        if os.path.isfile(os.path.join(input_directory, f)) and not f.lower().startswith('.') and f.lower().endswith('psv'):
            files.append(f)

    # TODO: implement output (Maybe scrap)
    #if not os.path.isdir(output_directory):
    #    os.mkdir(output_directory)

    data_arr = []
    label_arr = []
    # Iterate over files.
    for f in files:
        # Load data.
        input_file = os.path.join(input_directory, f)
        data,labels = load_challenge_data(input_file, split)
        data_arr.append(np.transpose(data))
        label_arr.append(labels)
        if len(data_arr) == limit:
            break

    return data_arr, label_arr

def data_process(dataset, expand_dims=False):
    '''
    preprocessing - expand dims to match largest '/home/wanglab/Osvald/CinC_data/training_setB'entry
    output is shape [n, time_steps, 40] np array
    each row is an hours worth of data
    TODO: edit labels to match utility funciton
          currently: 1 if past t_sepsis - 6, 0 otherwise
    '''
    n = len(dataset) # number of patients
    max_len = 0
    for i,pt in enumerate(dataset): #get max_len and remove NaN
        if pt.shape[1] > max_len:
            max_len = pt.shape[1]
        np.nan_to_num(pt, copy=False) #replaces NaN with zeros
        dataset[i] = pt.T

    if not expand_dims:
        return dataset

    for i, pt in enumerate(dataset): # expand dimensions to match largest input
        diff = max_len - pt.shape[0]
        if diff:
            pt = np.append(pt, np.ones((41, diff)).T * -1, axis=0)
        pt = np.expand_dims(pt, axis=0)

        #TODO: fix this very ugly workaround, here because of np flattening tendency
        if i == 0: 
            output = pt
        else:
            output = np.append(output, pt, axis=0)
    
    #data, labels = output[:,:,:-1], output[:,:,-1]
    return output #data, labels

def save_to_file(name, data, labels):
    np.save(name + '_data', data)
    np.save(name + '_labels', labels)

def load_from_file(name):
    data = np.load(name + '_data.npy', allow_pickle=True)
    labels = np.load(name + '_labels.npy', allow_pickle=True)
    print('\nLoaded data of shape:', data.shape)
    print('Loaded labels of shape:', labels.shape, '\n')
    return data, labels

class Dataset(data.Dataset):
  'Characterizes a dataset for PyTorch' #TODO: add option for gpu
  def __init__(self, IDs, path):
        self.IDs = IDs #list of IDs in dataset
        self.path = path

  def __len__(self):
        return len(self.IDs)

  def __getitem__(self, index):
        'Generates one sample of data'
        # Select sample
        ID = str(self.IDs[index])

        # Load data and get label
        # TODO: add arg for full path to data folder
        x = torch.load(self.path + ID + '.pt')
        y = x[:,-1].cuda()
        x = x[:,:-1].cuda()

        return x, y

def collate_fn(data):
    '''Creates mini-batch tensors from the list of tuples (image, caption).
    #TODO: add option for GPU
    Args:
        data: list of tuples (clinical vars, labels). 
            - clinical var: (n, 40) tensor.
            - labels : (n,1) tensor

    '''
    #sort by descending length w/in mini-batch
    data.sort(key=lambda x: len(x[1]), reverse=True)
    inputs, labels = zip(*data)
    max_len = inputs[0].shape[0]
    seq_len = [int(inputs[i].shape[0]) for i in range(len(inputs))]

    for i in range(len(inputs)):
        d_extension = (torch.ones((max_len - inputs[i].shape[0] ,40))*-1).cuda()
        l_extension = (torch.ones(max_len - inputs[i].shape[0])*-1).cuda()
        torch.cat((inputs[i], d_extension), dim=0, out = inputs[i])
        torch.cat((labels[i], l_extension), dim=0, out = labels[i])

    inputs = torch.stack(inputs, 0)
    labels = torch.stack(labels, 0)
    return inputs , labels , torch.as_tensor(seq_len, dtype=torch.double).cpu()

#TODO: turn these into functions
''' Load with no resizing example '''
#\train_data, _ = load_data(raw_dir, limit=100, split=False)
#train_data = data_process(train_data, expand_dims=False) # only tuns NaNs to zeros
#for i,pt in enumerate(train_data):
#    print(pt.shape)
#    torch.save(torch.from_numpy(pt), 'C:\\Users\\Osvald\\Sepsis_ML\\Sepsis_2019_PhysioNet\\vl_data\\'+str(i)+'.pt')
#save_to_file('/home/wanglab/Osvald/CinC_data/setB', train_data, train_labels)

'''Load with resizing example''' # data shape (n, 40, max_len) labels shape (n, max_len)
#train_data, _= load_data(raw_dir, limit=None, split=False)
#train_data = data_process(train_data, expand_dims=True)
#print(train_data.shape)

#for i,pt in enumerate(train_data):
#    torch.save(torch.from_numpy(pt), pth + str(i)+ '.pt')

#save_to_file(r'C:\Users\Osvald\Sepsis_ML\test', train_data, train_labels)

'''padding'''
#train_data, train_labels = load_data(raw_dir, limit=10, split=True)
#print([pt.shape for pt in train_data])
#train_data = data_process(train_data, expand_dims=True) # only tuns NaNs to zeros
#print([pt.shape for pt in train_data])
#lengths = [len(label) for label in train_labels]