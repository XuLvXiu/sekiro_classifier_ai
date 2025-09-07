#encoding=utf8
'''
train the classifier model
'''

import os
import shutil
import random
import sys
import pandas as pd
import torch
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Dataset
from torchvision.datasets import ImageFolder
from torchvision.models import resnet18, ResNet18_Weights
import torchmetrics


# step 1: rearrange images
df = pd.read_csv('labels.csv')
arr_y_grouped_count = df.groupby('y')['time'].count()
print('arr_y_grouped_count: \n', arr_y_grouped_count)

print('rearrange images...')
original_dir = 'images/original'
train_dir = 'images/train'
test_dir = 'images/test'

if os.path.exists(train_dir): 
    shutil.rmtree(train_dir)
if os.path.exists(test_dir): 
    shutil.rmtree(test_dir)

os.mkdir(train_dir)
os.mkdir(test_dir)
for i in [0, 1, 2]: 
    os.mkdir('%s/%s' % (train_dir, i))
    os.mkdir('%s/%s' % (test_dir, i))

obj_file_name_to_y = {}
for index, row in df.iterrows(): 
    img_file_i = row['img_file_i']
    time_colum = row['time']
    y = row['y']
    img_file_name = '%s_%s.jpg' % (time_colum, img_file_i)
    obj_file_name_to_y[img_file_name] = y

file_count = 0
arr_file_count = [0, 0, 0]
for file_name in os.listdir(original_dir): 
    # train-test: 70-30
    to_dir = train_dir
    if random.randint(1, 10) > 7: 
        to_dir = test_dir

    y = obj_file_name_to_y[file_name]
    to_path = '%s/%s/%s' % (to_dir, y, file_name)
    from_path = '%s/%s' % (original_dir, file_name)
    shutil.copyfile(from_path, to_path)
    file_count += 1
    arr_file_count[y] += 1

print('%s files copied, group: ' % (file_count), arr_file_count)

# step 2: train the model
print('train the model')
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomRotation(15),
    transforms.RandomGrayscale(p=0.5),
    # transforms.RandomHorizontalFlip(p=0.5),
    transforms.ToTensor(),
    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
])

dataset = ImageFolder(root=train_dir, transform=transform)
dataloader = DataLoader(dataset, batch_size=8, shuffle=True)

model = resnet18(weights=ResNet18_Weights.DEFAULT)
# print(model) 
num_classes = len(dataset.classes)
print('num_classes:', num_classes)
print(dataset.classes)

num_ftrs = model.fc.in_features
model.fc = torch.nn.Linear(num_ftrs, num_classes)

'''
for param in model.parameters():
    param.requires_grad = False
'''

if torch.cuda.is_available(): 
    model = model.cuda()

criterion = torch.nn.CrossEntropyLoss()
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

num_epochs = 40

train_accuracy = torchmetrics.classification.Accuracy(task="multiclass", num_classes=num_classes)

# why not using pytorch_lightning?
for epoch in range(num_epochs): 
    model.train()

    for inputs, labels in dataloader:
        optimizer.zero_grad()
        if torch.cuda.is_available(): 
            inputs = inputs.cuda()
            labels = labels.cuda()

        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        _, predicted = torch.max(outputs, 1)
        acc = train_accuracy(predicted.cpu(), labels.cpu())

    acc = train_accuracy.compute()
    train_accuracy.reset()
    print('epoch: %s/%s, loss: %s, acc: %s' % (epoch+1, num_epochs, 
        loss.item(), acc))


model_file_name = 'model.resnet.v1'
torch.save(model.state_dict(), model_file_name)

print('model saved')

# step 3: eval the model on the test set
print('eval the model on test set')
eval_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
])
dataset = ImageFolder(root=test_dir, transform=eval_transform)
dataloader = DataLoader(dataset, batch_size=8, shuffle=False)

model = resnet18(weights=ResNet18_Weights.DEFAULT)
num_classes = len(dataset.classes)
print('num_classes:', num_classes)
print(dataset.classes)

num_ftrs = model.fc.in_features
model.fc = torch.nn.Linear(num_ftrs, num_classes)

model.load_state_dict(torch.load(model_file_name))
model.eval()

if torch.cuda.is_available(): 
    model = model.cuda()

# total_loss = 0
correct_count = 0
total_count = 0
base_counter = {'0': 0, '1': 0, '2': 0}
obj_predicted_count = base_counter.copy()
obj_accuracy = base_counter.copy()
obj_correct_count = base_counter.copy()
obj_total_count = base_counter.copy()

eval_accuracy = torchmetrics.classification.Accuracy(task="multiclass", num_classes=num_classes)

with torch.no_grad():
    for inputs, labels in dataloader:
        if torch.cuda.is_available(): 
            inputs = inputs.cuda()
            labels = labels.cuda()

        outputs = model(inputs)
        loss = criterion(outputs, labels)
        # total_loss += loss.item()

        total_count += labels.size(0)
        _, predicted = torch.max(outputs, 1)
        correct_count += (predicted==labels).sum().item()

        predicted_list = predicted.cpu().numpy().tolist()
        acc = eval_accuracy(predicted.cpu(), labels.cpu())

        for i in range(0, len(predicted_list)): 
            pred_y = predicted_list[i]
            obj_predicted_count[str(pred_y)] += 1

            label = labels.cpu().numpy().tolist()[i]
            obj_total_count[str(label)] += 1
            if pred_y == label: 
                obj_correct_count[str(pred_y)] += 1

for i in ['0', '1', '2']: 
    obj_accuracy[i] = obj_correct_count[i] / (1 + obj_total_count[i])

print('eval accuracy: ', correct_count / total_count, ', correct_count:', correct_count, ', total_count:', total_count)
print('eval predicted: ', obj_predicted_count)
print('eval total_count: ', obj_total_count)
print('eval correct_count: ', obj_correct_count)
print('eval accuracy: ', obj_accuracy)

total_eval_accuracy = eval_accuracy.compute()
print('total_eval_accuracy:', total_eval_accuracy)
eval_accuracy.reset()
