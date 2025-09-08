#encoding=utf8

'''
reset the dataset
delete all the images and label csv file.
'''

import os
import shutil

image_dir = 'images'
if os.path.exists(image_dir): 
    shutil.rmtree(image_dir)
os.mkdir(image_dir)

original_dir = 'images/original'
os.mkdir(original_dir)

label_file = 'labels.csv'
if os.path.exists(label_file): 
    os.remove(label_file)

print('done')
