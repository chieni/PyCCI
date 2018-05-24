from main_application import *
from menu_bar import *
import tkFont
import tkFileDialog
import Tkinter as tk
import json, os, sys

def main(): 
	if getattr(sys, 'frozen', False):
	    application_path = os.path.dirname(sys.executable)
	elif __file__:
	    application_path = os.path.dirname(__file__)

	config_fname = os.path.join(application_path, 'config.json')
	print(config_fname)
	if not os.path.isfile(config_fname):
		print('Please make sure a "config.txt file" exists in this directory')
		return
		
	with open(config_fname) as f:
		config_data = json.load(f)
		title = config_data["title"]
		textbox_labels = config_data["textbox_labels"]
		textbox_label_to_key_dict = config_data["textbox_label_to_keypress"]
		labels_to_codes = config_data["textbox_label_to_code"]
		reviewer_labels = labels_to_codes.values()
		comment_boxes = config_data["comment_boxes"]
		checkbox_labels = config_data["checkbox_labels"]
		text_config = config_data["text_config"]
	
	root = tk.Tk()
	MainApplication(root, title, textbox_labels, checkbox_labels, comment_boxes, reviewer_labels, textbox_label_to_key_dict, labels_to_codes, text_config).pack(side="top", fill="both", expand=True)
	menubar = MenuBar(root)
	root.config(menu=menubar)
	root.mainloop()

if __name__ == '__main__':
    main()