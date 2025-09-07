#encoding=utf8

'''
在打游戏的过程中，收集游戏窗口截图、当时按下的按键，
保存到文件中


按 ] 键开始收集，再按一次结束收集
'''

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


# Event to control running state
running_event = mp.Event()


def signal_handler(sig, frame):
    log.debug("Gracefully exiting...")
    running_event.clear()
    sys.exit(0)

def wait_for_game_window():
    while True: 
        frame = grabscreen.grab_screen()
        if frame is not None and window.set_windows_offset(frame):
            log.debug("Game window detected and offsets set!")
            return True
        time.sleep(1)
    return False

# 动作结束时的回调函数
def on_action_finished():
    log.debug("动作执行完毕")

def flush_to_disk(arr_images, arr_keys): 
    log.info('begin to flush to disk')
    time_column = time.strftime('%Y%m%d_%H%M%S', time.localtime())
    if len(arr_images) == 0: 
        log.info('emtpy data: %s' % (time_column))
        return

    arr_y = []
    arr_img_file_i = []
    for i in range(0, len(arr_images)): 
        image = arr_images[i]
        key = arr_keys[i]
        y = 0
        if key == mouse.Button.left: 
            y = 1
        if key == mouse.Button.right: 
            y = 2
        arr_y.append(y)
        arr_img_file_i.append(i)
        cv2.imwrite('images/original/%s_%s.jpg' % (time_column, i), image)

    # create new df
    data = {
        'img_file_i': arr_img_file_i,
        'key': arr_keys,
        'y': arr_y,
    }
    df = pd.DataFrame(data)
    df['time'] = time_column

    csv_file_name = 'labels.csv'
    # read old df from csv file and merge it with the new data
    if os.path.exists(csv_file_name): 
        old_df = pd.read_csv(csv_file_name)
        df = pd.concat([old_df, df])

    df.to_csv(csv_file_name, index=False)
    log.info('end of flush to disk: %s %s' % (len(arr_images), df.shape[0]))


global_is_running = False
def main_loop(): 
    if not wait_for_game_window():
        log.debug("Failed to detect game window.")
        return

    arr_images = []
    arr_keys = []
    frame_count = 0
    while True: 
        log.info('main loop running')
        if not global_is_running: 
            # when the collector is not running, flush image and keys data to disk.
            if len(arr_images) > 0: 
                flush_to_disk(arr_images, arr_keys)
                # reset
                arr_images = []
                arr_keys = []
    
            time.sleep(1.0)
            continue

        t1 = time.time()

        frame = grabscreen.grab_screen()
        log.info('frame captured and will update all window')
        BaseWindow.set_frame(frame)
        BaseWindow.update_all()

        image = global_enemy_window.color.copy()
        arr_images.append(image)
        arr_keys.append(global_current_key)

        frame_count += 1

        t2 = time.time()
        log.info('main loop end one epoch, time: %.2f s' % (t2-t1))

        '''
        if frame_count == 150: 
            break
        '''


global_current_key = None
def on_press(key):
    # global global_current_key
    global global_is_running
    print('on_press key: ', key)
    try:
        if key == Key.esc: 
            log.info('The user presses Esc in the game, will terminate.')
            os._exit(0)

        # global_current_key = key

        if hasattr(key, 'char') and key.char == ']': 
            # switch the switch
            if global_is_running: 
                global_is_running = False
            else: 
                global_is_running = True

    except Exception as e:
        print(e)

def on_click(x, y, button, pressed): 
    global global_current_key
    if pressed: 
        print('on_click click button:', button)
        global_current_key = button
    else: 
        print('on_click release button:', button)
        global_current_key = None


def main():
    signal.signal(signal.SIGINT, signal_handler)

    keyboard_listener = Listener(on_press=on_press)
    keyboard_listener.start()
    log.info('keyboard listener setup. press Esc to exit')

    mouse_listener = mouse.Listener(on_click=on_click)
    mouse_listener.start()
    log.info('mouse listener setup.')

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
