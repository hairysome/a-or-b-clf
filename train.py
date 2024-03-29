# Author: Jithin James
# Adapted from: https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html

from __future__ import print_function, division
import argparse

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
import numpy as np
import torchvision
from torchvision import datasets, models, transforms
import matplotlib.pyplot as plt
import time
import os
import copy

import utils
from classificationService import AntOrBeeClassifier

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
epoch = 0

def train_model(dataloaders, dataset_sizes, model, criterion, optimizer, scheduler, start_epoch, end_epoch):
    global device, epoch
    since = time.time()

    best_model_wts = copy.deepcopy(model.state_dict())
    best_acc = 0.0

    for epoch in range(start_epoch, end_epoch):
        print('Epoch {}/{}'.format(epoch, end_epoch - 1))
        print('-' * 10)

        # Each epoch has a training and validation phase
        for phase in ['train', 'val']:
            if phase == 'train':
                model.train()  # Set model to training mode
            else:
                model.eval()   # Set model to evaluate mode

            running_loss = 0.0
            running_corrects = 0

            # Iterate over data.
            for inputs, labels in dataloaders[phase]:
                inputs = inputs.to(device)
                labels = labels.to(device)

                # zero the parameter gradients
                optimizer.zero_grad()

                # forward
                # track history if only in train
                with torch.set_grad_enabled(phase == 'train'):
                    outputs = model(inputs)
                    _, preds = torch.max(outputs, 1)
                    loss = criterion(outputs, labels)

                    # backward + optimize only if in training phase
                    if phase == 'train':
                        loss.backward()
                        optimizer.step()

                # statistics
                running_loss += loss.item() * inputs.size(0)
                running_corrects += torch.sum(preds == labels.data)
            if phase == 'train':
                scheduler.step()

            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects.double() / dataset_sizes[phase]

            print('{} Loss: {:.4f} Acc: {:.4f}'.format(
                phase, epoch_loss, epoch_acc))

            # deep copy the model
            if phase == 'val' and epoch_acc > best_acc:
                best_acc = epoch_acc
                best_model_wts = copy.deepcopy(model.state_dict())

        print()

    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
    print('Best val Acc: {:4f}'.format(best_acc))

    # load best model weights
    model.load_state_dict(best_model_wts)
    return model

def main(checkpoint=None):
    global epoch
    # Data augmentation and normalization for training
    # Just normalization for validation
    data_transforms = {
        'train': transforms.Compose([
            transforms.RandomResizedCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
        'val': transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ]),
    }

    data_dir = 'data'
    image_datasets = {x: datasets.ImageFolder(os.path.join(data_dir, x),
                                              data_transforms[x])
                      for x in ['train', 'val']}
    dataloaders = {x: torch.utils.data.DataLoader(image_datasets[x], batch_size=4,
                                                 shuffle=True, num_workers=0)
                  for x in ['train', 'val']}
    dataset_sizes = {x: len(image_datasets[x]) for x in ['train', 'val']}
    class_names = image_datasets['train'].classes



    model_ft = models.resnet18(pretrained=True)
    num_ftrs = model_ft.fc.in_features
    # Here the size of each output sample is set to 2.
    # Alternatively, it can be generalized to nn.Linear(num_ftrs, len(class_names)).
    model_ft.fc = nn.Linear(num_ftrs, 2)

    if checkpoint is None:
        model_ft = model_ft.to(device)

        criterion = nn.CrossEntropyLoss()

        # Observe that all parameters are being optimized
        optimizer_ft = optim.SGD(model_ft.parameters(), lr=0.001, momentum=0.9)

        # Decay LR by a factor of 0.1 every 7 epochs
        exp_lr_scheduler = lr_scheduler.StepLR(optimizer_ft, step_size=7, gamma=0.1)

    else:
        model_state_dict, criterion, optimizer_ft, exp_lr_scheduler, epoch = utils.load_model(checkpoint)
        model_ft.load_state_dict(model_state_dict)
        model_ft = model_ft.to(device)
    try:
        model_ft = train_model(dataloaders, dataset_sizes, model_ft, criterion,
            optimizer_ft, exp_lr_scheduler, start_epoch=epoch, end_epoch=10)

        saveToBento = input("Save model to Bento ML (yes/no): ")

        if saveToBento.lower() == "yes":
            # Add it to BentoML
            bento_svc = AntOrBeeClassifier()
            bento_svc.pack('model', model_ft)

            # Save your Bento Service
            saved_path = bento_svc.save()
            print('Bento Service saved in ', saved_path)

            #Copy Bento Service to git dir
            git_dir = "/home/project/AntOrBeeClassifier/my-a-or-b/"
            cmd = 'cp -r '+saved_path+'/. '+git_dir
            os.system(cmd)
            
    except KeyboardInterrupt:
        pass
    finally:
        utils.save_model(model_ft, criterion, optimizer_ft, exp_lr_scheduler,
                epoch)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--checkpoint',
        help='Specify a checkpoint file to load from')
    args = parser.parse_args()

    if args.checkpoint:
        main(args.checkpoint)
    else:
        main()
