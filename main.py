#encoding=utf8

'''
main
'''
print('importing...')

import multiprocessing as mp
import time
import sys
import signal
import cv2

from utils import change_window
import window
from window import BaseWindow, global_enemy_window
import grabscreen
from log import log
from actions import ActionExecutor
from pynput.keyboard import Listener, Key
from pynput import mouse
import os
import numpy as np
import pandas as pd

import torch
import torchvision.transforms as transforms
from torchvision.models import resnet18, ResNet18_Weights
from PIL import Image


# load model
eval_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
])

arr_action_name = ['IDLE', 'ATTACK', 'PARRY', 'SHIPO', 'JUMP']
model = resnet18(weights=ResNet18_Weights.DEFAULT)
# -1 是因为弦一郎一阶段不需要 jump 
num_classes = len(arr_action_name) - 1
print('num_classes:', num_classes)

num_ftrs = model.fc.in_features
model.fc = torch.nn.Linear(num_ftrs, num_classes)

model_file_name = 'model.resnet.v1'
model.load_state_dict(torch.load(model_file_name))
model.eval()

if torch.cuda.is_available(): 
    model = model.cuda()

# Event to control running state
running_event = mp.Event()


def signal_handler(sig, frame):
    log.debug("Gracefully exiting...")
    running_event.clear()
    executor.interrupt_action()
    sys.exit(0)

def wait_for_game_window():
    while True: 
        frame = grabscreen.grab_screen()
        if frame is not None and window.set_windows_offset(frame):
            log.debug("Game window detected and offsets set!")

            BaseWindow.set_frame(frame)
            BaseWindow.update_all()

            log.debug('waiting for model loading...')
            image = global_enemy_window.color.copy()
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image)
            pil_image = eval_transform(pil_image)
            inputs = pil_image.unsqueeze(0)

            with torch.no_grad(): 
                if torch.cuda.is_available(): 
                    inputs = inputs.cuda()

                outputs = model(inputs)

            return True
        time.sleep(1)
    return False

# 动作结束时的回调函数
def on_action_finished():
    log.debug("action execute finished")

global_is_running = False
executor = ActionExecutor('./config/actions_conf.yaml')

def main_loop(): 
    if not wait_for_game_window():
        log.debug("Failed to detect game window.")
        return

    frame_count = 0
    ATTACK_ACTION_ID = 1
    PARRY_ACTION_ID = 2
    previous_action_id = None
    while True: 
        log.info('main loop running')
        if not global_is_running: 
            previous_action_id = None
            time.sleep(1.0)
            continue

        t1 = time.time()

        frame = grabscreen.grab_screen()
        log.info('frame captured and will update all window')
        BaseWindow.set_frame(frame)
        BaseWindow.update_all()

        image = global_enemy_window.color.copy()
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image)
        pil_image = eval_transform(pil_image)
        inputs = pil_image.unsqueeze(0)

        action_id = None
        with torch.no_grad(): 
            # inputs: torch.Size([1, 3, 224, 224])
            # print('inputs:', inputs.shape)
            if torch.cuda.is_available(): 
                inputs = inputs.cuda()

            outputs = model(inputs)
            _, predicted = torch.max(outputs, 1)

            # 0, 1, 2, 3, 4
            action_id = predicted.item()

            # no idle
            # if you want to idle, please parry.
            if action_id == 0: 
                action_id = PARRY_ACTION_ID

            '''
            # 不贪刀
            if action_id == ATTACK_ACTION_ID and previous_action_id == ATTACK_ACTION_ID: 
                action_id = PARRY_ACTION_ID
            '''

        action_name = arr_action_name[action_id]

        '''
        # 多贪一刀
        if action_name == 'ATTACK': 
            action_name = 'DOUBLE_ATTACK'
        '''

        log.debug('previous_action_id: %s, action_id: %s' % (previous_action_id, action_id))
        '''
        如果现在要防御, 那么需要判断前一个动作是否为防御，
            如果前一个动作也为防御，则 IDLE 即可，因为此时还未释放右键
        如果现在不要防御，那么也需要判断前一个动作是否为防御，
            如果前一个动作为防御，那么需要释放右键才能进行本次的动作。
        '''
        if action_id == PARRY_ACTION_ID and previous_action_id == PARRY_ACTION_ID: 
            action_name = 'IDLE'
        if (not action_id == PARRY_ACTION_ID) and previous_action_id == PARRY_ACTION_ID: 
            log.debug('take_action: %s' % ('RELEASE_PARRY'))
            executor.take_action('RELEASE_PARRY', action_finished_callback=on_action_finished)
            '''
            while executor.is_running(): 
                time.sleep(0.02)
            '''

        log.debug('take_action: %s' % (action_name))
        executor.take_action(action_name, action_finished_callback=on_action_finished)

        while executor.is_running(): 
            time.sleep(0.05)
        previous_action_id = action_id

        frame_count += 1

        t2 = time.time()
        log.info('main loop end one epoch, time: %.2f s' % (t2-t1))

        '''
        if frame_count == 150: 
            break
        '''


# global_current_key = None
def on_press(key):
    # global global_current_key
    global global_is_running
    # print('on_press key: ', key)
    try:
        if key == Key.backspace: 
            log.info('The user presses backspace in the game, will terminate.')
            executor.interrupt_action()
            os._exit(0)

        # global_current_key = key

        if hasattr(key, 'char') and key.char == ']': 
            # switch the switch
            if global_is_running: 
                global_is_running = False
                executor.interrupt_action()
            else: 
                global_is_running = True

    except Exception as e:
        print(e)

'''
def on_click(x, y, button, pressed): 
    global global_current_key
    if pressed: 
        # print('on_click click button:', button)
        global_current_key = button
    else: 
        # print('on_click release button:', button)
        global_current_key = None
'''

def main():
    signal.signal(signal.SIGINT, signal_handler)

    keyboard_listener = Listener(on_press=on_press)
    keyboard_listener.start()
    log.info('keyboard listener setup. press backspace to exit')

    '''
    mouse_listener = mouse.Listener(on_click=on_click)
    mouse_listener.start()
    log.info('mouse listener setup.')
    '''

    # Initialize camera
    grabscreen.init_camera(target_fps=5)

    change_window.correction_window()

    if change_window.check_window_resolution_same(window.game_width, window.game_height) == False:
        raise ValueError(
            f"游戏分辨率和配置game_width({window.game_width}), game_height({window.game_height})不一致，请到window.py中修改"
        )
    
    main_loop()


if __name__ == '__main__':
    main()
