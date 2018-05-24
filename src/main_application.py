from annotation_panel import *
import ast
import csv
import numpy as np
import os
import pandas as pd
from ScrolledText import ScrolledText
import sys
import re
import time
import tkFont
import tkFileDialog
import Tkinter as tk
from PIL import ImageTk, Image
import tkMessageBox


class MainApplication(tk.Frame):
    def __init__(self, master, title, textbox_labels, checkbox_labels, comment_boxes, reviewer_labels, textbox_labels_to_key_dict, labels_to_codes, text_config):
        self.master = master
        self.title = title
        self.textbox_labels_to_key_dict = textbox_labels_to_key_dict
        self.reviewer_labels = reviewer_labels
        self.labels_to_codes = labels_to_codes
        self.text_config = text_config
        tk.Frame.__init__(self, self.master)
       
        # Define variables

        # Text strings
        self.title_text = "\t\t" + self.title
        
        # Flags
        self.is_comparison_mode = False

        # Indices
        self.current_row_index = 0
        self.current_row_id = None
        self.current_results_index = 0
        self.current_results_id = None

        # Filenames
        self.file = None
        self.results_filename = None
        self.keywords_fname = self.text_config['keywords_fname']
        self.review_fname = None
        
        # Dataframes
        self.total_notes_df = None # Used on comparison mode
        self.results_df = None
        self.data_df = None
        self.review_df = None
        
        # Lists and Dicts
        self.tag_label_dict = {}
        self.keywords_list = []
        self.review_row_ids = []
        self.review_tag_label_dict = {}

        # Create GUI
        self._define_fonts()
        self._create_body()
        self.annotation_panel = AnnotationPanel(master, self.checkframe, textbox_labels, comment_boxes, checkbox_labels, textbox_labels_to_key_dict, labels_to_codes, text_config)
        self.annotation_panel.pack()

    # GUI Setup functions and helper functions
    def _define_fonts(self):
        self.titlefont = tkFont.Font(size=16, weight='bold')
        self.boldfont = tkFont.Font(size=14, weight='bold')
        self.textfont = tkFont.Font(family='Helvetica', size=15)
        self.h3font = tkFont.Font(size=11)

    def _resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def _clean_text(self, text):
        if type(text) == float:
            return text
        cleaned = str(text.replace('\r\r', '\n').replace('\r', ''))
        cleaned = re.sub(r'\n+', '\n', cleaned)
        cleaned = re.sub(r' +', ' ', cleaned)
        cleaned = re.sub(r'\t', ' ', cleaned)
        return str(cleaned.strip())

    # Opening file functions
    def openfile(self):
        if self.file is not None:
            # TODO: Popup
            return

        self.file = tkFileDialog.askopenfilename()
        if not self.file:
            return

        self.is_comparison_mode = False
        self.data_df = pd.read_csv(self.file)
        # Clean all the text fields
        self.data_df[self.text_config['text_key']] = self.data_df[self.text_config['text_key']].map(lambda text: self._clean_text(text))

        # Read in all keywords
        self.keywords_fname = '/'.join(self.file.split("/")[:-1]) + '/' + self.keywords_fname
        if os.path.isfile(self.keywords_fname):
            with open(self.keywords_fname, 'r') as f:
                self.keywords_list = f.readlines()
                self.keywords_list = [l.strip() for l in self.keywords_list]

        # If the file already exists, open it and continue at the spot you were,
        # makes it easier to continue on annotating results
        self.results_filename = self.file[:-4] + self.text_config['results_fname_suffix']
        if os.path.isfile(self.results_filename):
            self.results_df = pd.read_csv(self.results_filename, index_col=0, header=0)
            # Find iloc of ROW_ID in data_df. Crane to this position.
            if self.text_config['note_key'] in self.results_df and self.results_df.shape[0] > 0:
                last_row_id = self.results_df.iloc[-1][self.text_config['note_key']]
                crane_to = self.data_df[self.data_df[self.text_config['note_key']] == last_row_id].index.tolist()[0]
                self._change_note(crane_to + 1)
            else:
                self._change_note(0)
        else:
            self._change_note(0)

    # Create display functions
    def _create_display_values(self, current_note_num, total, admission_id, note_category, clin_text):
        # Fill display values
        self.ptnumber.config(text=str(current_note_num + 1))
        self.pttotal.config(text=str(total))

        self.pthAdm.config(text=admission_id)
        self.ptnotetype.config(text=note_category)

        # Box that displays patient text
        self.pttext.config(state=tk.NORMAL)
        self.pttext.delete(1.0, tk.END)
        self.pttext.insert(tk.END, clin_text)
        self.pttext.config(state=tk.DISABLED)

        self.pttext.bind("<Command-c>", self._on_copy)

        for textbox_label, key in self.textbox_labels_to_key_dict.iteritems():
            def make_lambda(k, t):
                return lambda ev: self._do_key_click(ev, k, t)
            self.pttext.bind("<KeyPress-%c>" % key, make_lambda(key, textbox_label))

        self.pttext.tag_config('keyword', background='lightgoldenrod2')
        self.pttext.tag_config('labelled', background='cadetblue1')
        self.pttext.tag_config('overlapping', background='cadetblue3')
        
        self.pttext.tag_bind("labelled", "<Button-1>", lambda event: self._on_label_tag_click(event, 'labelled'))
        self.pttext.tag_bind("overlapping", "<Button-1>", lambda event: self._on_label_tag_click(event, 'overlapping'))
        
        self.pttext.tag_raise("labelled")
        self.pttext.tag_raise("overlapping")
        self.pttext.tag_raise("sel")
        self.add_keyword_highlighting()
        self.add_highlighting()

    # Open a results file where annotations can be viewed and edited
    def open_results_file(self):
        comparison_files = tkFileDialog.askopenfilenames(parent=self.master, title='Select annotated files')
        comparison_files = self.master.tk.splitlist(comparison_files)

        self.is_comparison_mode = True
        self.review_fname = '/'.join(comparison_files[0].split('/')[:-1]) + '/' + self.text_config['review_fname']
        comparison_dfs = []

        for fname in comparison_files:
            df = pd.read_csv(fname, index_col=0, header=0)
            df[self.text_config['text_key']] = df[self.text_config['text_key']].map(lambda text: self._clean_text(text))
            comparison_dfs.append(df)

        for df in comparison_dfs:
            self.review_row_ids += df[self.text_config['note_key']].unique().tolist()
        self.review_row_ids = list(set(self.review_row_ids))
        # if review df file exists, open.
        if os.path.isfile(self.review_fname):
            self.review_df = pd.read_csv(self.review_fname, index_col=0, header=0)
            self.review_df['REVIEWER_LABELS'] = self.review_df['REVIEWER_LABELS'].astype(object)
            # Pop up that existing review file is being opened. 
        # Create a whole new review_df
        else:
            reviewer_dicts = []
            for row_id in self.review_row_ids:
                reviewer_dicts += self.create_review_dict_for_note(row_id, comparison_dfs)
            self.review_df = pd.DataFrame(reviewer_dicts)
            self.review_df.index = np.arange(self.review_df.shape[0])
            self.review_df = self.review_df[[self.text_config['note_key'], self.text_config['text_key'], 'LABELLED_TEXT', 'START', 'LABELS', 'ANNOTATORS', 'REVIEWER_LABELS']]
            self.review_df['REVIEWER_LABELS'] = self.review_df['REVIEWER_LABELS'].astype(object)
            self.review_df.to_csv(self.review_fname)
        # Navigate to first note (change_review_note)
        self._change_review_note(0)

    def crane(self, delta, results_filename):
        '''
        Called whenever you press back or next
        '''
        # Save labels changed
        if self.is_comparison_mode:
            is_saved = self.save_annotations()
            self._change_review_note(delta)
        else:
            is_saved = self.save_annotations()
            self._change_note(delta)

    def _change_note(self, delta):
        num_notes = self.data_df.shape[0]
        self.current_row_index += delta
        if self.current_row_index < 1:
            self.current_row_index = 0

        if self.current_row_index > num_notes-1:
            self.current_row_index = num_notes-1
        self.current_row_id = self.data_df[self.text_config['note_key']].iloc[self.current_row_index]
        admission_id = self.data_df[self.text_config['note_key']].iloc[self.current_row_index]
        note_category = self.data_df[self.text_config['category_key']].iloc[self.current_row_index]
        clin_text = self.data_df[self.text_config['text_key']].iloc[self.current_row_index]
        self._create_display_values(self.current_row_index, num_notes, admission_id, note_category, clin_text)

    def save_annotations(self):
        if self.is_comparison_mode:
            new_results_df = self.annotation_panel.save_review_annotations(self.review_df, self.current_results_id)
            if new_results_df is not None:
                self.review_df = new_results_df
                self.review_df.to_csv(self.review_fname)
                self.add_review_highlighting()
        else:
            new_results_df = self.annotation_panel.save_annotations(self.data_df, self.current_row_index, self.results_df)
            if new_results_df is not None:
                self.results_df = new_results_df
                self.results_df.to_csv(self.results_filename)
                # Refresh display values
                self.add_keyword_highlighting()
                self.add_highlighting()

    # For one note
    def create_review_dict_for_note(self, current_note_id, comparison_dfs):
        current_note_text = None
        annotator_dict = {}
        for i, df in enumerate(comparison_dfs):
            current_results_df = df[(df[self.text_config['note_key']] == current_note_id) & (df['NO_LABELS'] == 0)]
            phrases_dict = {}
            for j, row in current_results_df.iterrows():
                if current_note_text:
                    assert row[self.text_config['text_key']] == current_note_text
                current_note_text = row[self.text_config['text_key']]
                text_start = int(row['START'])
                text_end = int(row['START'] + len(row['LABELLED_TEXT']))
                current_label = row['LABEL']
                
                if (text_start, text_end) in phrases_dict:
                    phrases_dict[(text_start, text_end)].append(current_label)

                else:
                    phrases_dict[(text_start, text_end)] = [current_label]

            annotator_dict['annotator' + str(i)] = self.retrieve_label_groups(phrases_dict)
        #ROW_ID, TEXT, LABELLED_TEXT, LABELs, ANNOTATORS, REVIEWER_LABELS
        reviewer_dicts = []
        for interval, ann_tag_data in self.retrieve_annotator_label_groups(annotator_dict).iteritems():
            labels = []
            annotators = []
            for key, val in ann_tag_data.annotator_to_labels.iteritems():
                annotators.append(key)
                labels.append(val.labels)
            reviewer_dict = {
            self.text_config['note_key']: current_note_id,
            self.text_config['text_key']: current_note_text,
            'LABELLED_TEXT': current_note_text[interval[0]:interval[1]],
            'START': interval[0],
            'LABELS': labels,
            'ANNOTATORS': annotators,
            'REVIEWER_LABELS': None
            }
            reviewer_dicts.append(reviewer_dict)
        return reviewer_dicts

    # Creates items displayed in the notes panel. Adds highlights if in comparison mode.
    def _create_review_display_values(self, current_note_num, total, admission_id, note_category, clin_text):
        # Fill display values
        self.ptnumber.config(text=str(current_note_num + 1))
        self.pttotal.config(text=str(total))

        self.pthAdm.config(text=admission_id)
        if note_category:   
            self.ptnotetype.config(text=note_category)

        # Box that displays patient text
        self.pttext.config(state=tk.NORMAL)
        self.pttext.delete(1.0, tk.END)
        self.pttext.insert(tk.END, clin_text)
        self.pttext.config(state=tk.DISABLED)
        # Add highlighting
        # Config tags
        self.pttext.tag_config('agree', background='green yellow')
        self.pttext.tag_config('disagree', background='indian red')
        self.pttext.tag_config('reviewed', background='skyblue')
        self.pttext.tag_config('single', background='indian red')
        self.pttext.tag_bind("agree", "<Button-1>", lambda event: self._on_review_tag_click(event, 'agree'))
        self.pttext.tag_bind("disagree", "<Button-1>", lambda event: self._on_review_tag_click(event, 'disagree'))
        self.pttext.tag_bind("reviewed", "<Button-1>", lambda event: self._on_review_tag_click(event, 'reviewed'))
        self.pttext.tag_bind("single", "<Button-1>", lambda event: self._on_review_tag_click(event, 'reviewed'))
        self.add_review_highlighting()

    def _change_review_note(self, delta):
        num_notes = len(self.review_row_ids)
        self.current_results_index += delta
        if self.current_results_index < 1:
            self.current_results_index = 0
        if self.current_results_index > num_notes-1:
            self.current_results_index = num_notes-1
        self.current_results_id = self.review_row_ids[self.current_results_index]
        admission_id = self.current_results_id
        note_category = None
        clin_text = self.review_df[self.review_df[self.text_config['note_key']] == self.current_results_id][self.text_config['text_key']].values.tolist()[0]
        self._create_review_display_values(self.current_results_index, num_notes, admission_id, note_category, clin_text)

    def _create_body(self):
        width, height = 1200, self.master.winfo_screenheight()/1.1
        self.main_window = tk.PanedWindow(self.master, height=height, width=width, orient=tk.VERTICAL)
        self.main_window.pack(fill=tk.BOTH, expand=True)

        # Title
        self.master.title(self.title + " PyCCI")
        self.upper_section = tk.PanedWindow(self.main_window)
        self.main_window.add(self.upper_section, padx=10, pady=10)

        self.openbutton = tk.Button(self.upper_section,
                                 text="Open CSV",
                                 command=self.openfile,
                                 padx=15)
        self.openbutton.place(anchor=tk.W, x=20, rely=0.25)

        self.otherb = tk.Button(self.upper_section,
                                 text="Open Results",
                                 command=self.open_results_file,
                                 padx=15)
        self.otherb.place(anchor=tk.W, x=130, rely=0.25)

        image = Image.open(self._resource_path('CCI.png'))
        photo = ImageTk.PhotoImage(image)
      
        self.panel = tk.Label(self.upper_section, image=photo)
        self.panel.image = photo
        self.panel.pack(side=tk.RIGHT, padx=10)

        tk.Label(self.upper_section, text=self.title_text,
              font=self.titlefont,
              fg="dodgerblue4").pack()

        # Panes below buttons
        self.bottom_section = tk.PanedWindow(self.main_window)
        self.bottom_section.pack(fill=tk.BOTH, expand=True)
        self.main_window.add(self.bottom_section)
        self.leftpane = tk.PanedWindow(self.bottom_section)
        self.bottom_section.add(self.leftpane,
                    width=600,
                    padx=20)
        self.separator = tk.PanedWindow(self.bottom_section,
                                     relief=tk.SUNKEN)
        self.bottom_section.add(self.separator,
                    width=2,
                    padx=5,
                    pady=30)
        self.rightpane = tk.PanedWindow(self.bottom_section)
        self.bottom_section.add(self.rightpane, width=400)

        self.ptframe = tk.LabelFrame(self.leftpane,
                                  text="Medical Record",
                                  font=self.boldfont,
                                  padx=0,
                                  pady=10,
                                  borderwidth=0)
        self.ptframe.pack(fill=tk.BOTH, expand=True)

        self.ptnumberframe = tk.Frame(self.ptframe,
                                   padx=6,
                                   pady=3,
                                   borderwidth=0)
        self.ptnumberframe.pack()

        self.ptnumber_A = tk.Label(self.ptnumberframe, text="Note", fg="dodgerblue4")
        self.ptnumber_A.grid(row=1, column=0, sticky=tk.E)
        self.ptnumber = tk.Label(self.ptnumberframe, text=" ")
        self.ptnumber.grid(row=1, column=1)
        self.ptnumber_B = tk.Label(self.ptnumberframe, text="of", fg="dodgerblue4")
        self.ptnumber_B.grid(row=1, column=2)
        self.pttotal = tk.Label(self.ptnumberframe, text=" ")
        self.pttotal.grid(row=1, column=3)

        self.ptframeinfo = tk.Frame(self.ptframe,
                                 padx=0,
                                 pady=3,
                                 borderwidth=0)
        self.ptframeinfo.pack()

        self.phAdm_ = tk.Label(self.ptframeinfo, text="Hospital Admission ID:", fg="dodgerblue4")
        self.phAdm_.grid(row=2, column=0, sticky=tk.E)
        self.pthAdm = tk.Label(self.ptframeinfo, text=" ", font=self.h3font)
        self.pthAdm.grid(row=2, column=1, sticky=tk.W)

        self.ptnotetype_ = tk.Label(self.ptframeinfo, text="Note Type:", fg="dodgerblue4")
        self.ptnotetype_.grid(row=3, column=0, sticky=tk.E)
        self.ptnotetype = tk.Label(self.ptframeinfo, text=" ", font=self.h3font)
        self.ptnotetype.grid(row=3, column=1, sticky=tk.W)

        # Incrementer buttons
        self.buttonframe = tk.Frame(self.ptframe)
        self.buttonframe.pack()
        self.buttonframe.place(relx=0.97, anchor=tk.NE)
        # Back Button
        self.back_button = tk.Button(self.buttonframe,
                              text='Back',
                              width=6,
                              command=lambda: self.crane(-1, self.results_filename))  # Argument is -1, decrement
        self.back_button.grid(row=0, column=0, padx=2, pady=0)
        # Next Button
        self.next_button = tk.Button(self.buttonframe,
                              text='Next',
                              width=6,
                              command=lambda: self.crane(1, self.results_filename))  # Argument is 1, increment
        self.next_button.grid(row=0, column=2, padx=2, pady=0)

        text_frame = tk.Frame(self.ptframe, borderwidth=1, relief="sunken")
        self.pttext = tk.Text(wrap="word", background="white", 
                            borderwidth=0, highlightthickness=0)
        self.vsb = tk.Scrollbar(orient="vertical", borderwidth=1,
                                command=self.pttext.yview)
        self.pttext.configure(yscrollcommand=self.vsb.set, font=self.textfont, padx=20, pady=20)
        self.vsb.pack(in_=text_frame,side="right", fill="y", expand=False)
        self.pttext.pack(in_=text_frame, side="left", fill="both", expand=True)
        self.pttext.bind("<1>", lambda event: self.pttext.focus_set())
        text_frame.pack(fill="both", expand=True)


        # Below buttons
        self.submit_frame = tk.Frame(self.ptframe)
        self.submit_frame.pack(side=tk.RIGHT)
        self.submit_button = tk.Button(self.submit_frame,
                                       text='Save Annotation',
                                       width=14,
                                       command=self.save_annotations)
        self.submit_button.grid(row=0, column=0, padx=2, pady=10)

        # Create canvas with scrollbar
        canvas = tk.Canvas(self.rightpane)
        scrollbar = tk.Scrollbar(self.rightpane, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        canvas.pack(side=tk.LEFT, fill='both', expand=True)
        
        # put frame in canvas

        self.checkframe = tk.LabelFrame(canvas, text="Indicators",
                                     font=self.boldfont,
                                     padx=10,
                                     pady=20,
                                     borderwidth=0)
        canvas.create_window((0,0), window=self.checkframe, anchor='nw', tags='self.checkframe')
        self.checkframe.bind('<Configure>', lambda event: self.on_configure(event,canvas))


        #self.checkframe.pack(fill=tk.BOTH, expand=True)
        self._create_display_values(0, 1, "NA", "NA", "Please use the ''Open CSV'' button to open the .csv file provided to you, "
                           + "for example:\n'dischargeSummaries29JUN16.csv'\n"
                           + "This will create a 'results' file within the same directory.")

    def on_configure(self, event, canvas):
        canvas.configure(scrollregion=canvas.bbox('all'))

    # TAG FUNCTIONALITY CODE
    ## For annotation version

    # Keypress functions
    def _on_copy(self, event):
        count = int(self.master.call(event.widget, "count", "1.0", "sel.first"))
        text = event.widget.get('sel.first', 'sel.last')
        alpha_start = re.search(r'\w', text).start()
        self.annotation_panel.last_highlighted_char_index = count + alpha_start
        self.annotation_panel.last_highlighted_text = text.strip()

    def _do_key_click(self, event, key, textbox_label):
        if event.widget.tag_ranges(tk.SEL):
            start = int(self.master.call(event.widget, "count", "1.0", "sel.first"))
            text = event.widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.annotation_panel.add_text_to_textbox(start, text, textbox_label)

    # Label highlighting functions
    def add_highlighting(self):
        start = '1.0'
        self._remove_all_tags('labelled')
        self._remove_all_tags('overlapping')
        if self.results_df is not None:
            current_results_df = self.results_df[(self.results_df[self.text_config['note_key']] == self.current_row_id) & (self.results_df['NO_LABELS'] == 0)]
            phrases_dict = {}
            for i, row in current_results_df.iterrows():
                note_text = row[self.text_config['text_key']]
                text_start = int(row['START'])
                text_end = int(row['START'] + len(row['LABELLED_TEXT']))
                current_label = row['LABEL']
                
                if (text_start, text_end) in phrases_dict:
                    phrases_dict[(text_start, text_end)].append(current_label)

                else:
                    phrases_dict[(text_start, text_end)] = [current_label]

            # Sort endpoints and consolidate intervals
            self.current_label_groups_dict = self.retrieve_label_groups(phrases_dict)
            for interval, tag_data in self.current_label_groups_dict.iteritems():
                pos_start = '{}+{}c'.format(start, interval[0])
                pos_end = '{}+{}c'.format(start, interval[1])
                if len(tag_data.labels) > 1:
                    self.pttext.tag_add('overlapping', pos_start, pos_end)
                else:
                    self.pttext.tag_add('labelled', pos_start, pos_end)

    def add_keyword_highlighting(self):
        start = '1.0'
        self._remove_all_tags('keyword')
        if not self.current_row_index:
            return
        current_note_text = self.data_df[self.text_config['text_key']].iloc[self.current_row_index]
        for phrase in self.keywords_list:
            try:
                matches = [m.start() for m in re.finditer(phrase, current_note_text)]
                for match in matches:
                    pos_start = '{}+{}c'.format(start, match)
                    pos_end = '{}+{}c'.format(start, match + len(phrase))
                    self.pttext.tag_add('keyword', pos_start, pos_end)
            except:
                return

    def _remove_all_tags(self, tag_name):
        # Remove any existing tags
        tag_indices = list(self.pttext.tag_ranges(tag_name))
        # iterate them pairwise (start and end index)
        for start, end in zip(tag_indices[0::2], tag_indices[1::2]):
            self.pttext.tag_remove(tag_name, start, end)

    def _delete_label_tag(self, starts, label):
        for start in starts:
            self.results_df = self.results_df[~((self.results_df[self.text_config['note_key']] == self.current_row_id) & (self.results_df['START'] == start) & (self.results_df['LABEL'] == label))]
        self.add_keyword_highlighting()
        self.add_highlighting()

    def _on_label_tag_click(self, event, tag_name):
        # get the index of the mouse click
        index = event.widget.index("@%s,%s" % (event.x, event.y))
        tag_indices = list(event.widget.tag_ranges(tag_name))
        click_pos = int(self.master.call(event.widget, "count", "1.0", index))
        # iterate them pairwise (start and end index)
        for interval, tag_data in self.current_label_groups_dict.iteritems():
            starts = tag_data.starts
            if interval[0] <= click_pos <= interval[1]:
                popup_menu = tk.Menu(self.master, tearoff=0)

                for label in tag_data.labels:
                    popup_menu.add_command(label=label, command='')
                # Add separator
                popup_menu.add_separator()
                delete_menu = tk.Menu(popup_menu, tearoff=0)
                for label in tag_data.labels:
                    delete_menu.add_command(label=label, command=lambda (starts, label) = (starts, label): self._delete_label_tag(starts, label))
                popup_menu.add_cascade(label="Delete", menu=delete_menu)
                popup_menu.tk_popup(event.x_root, event.y_root, 0)
   
    ## For review version
    def add_review_highlighting(self):
        start = '1.0'
        self._remove_all_tags('agree')
        self._remove_all_tags('disagree')
        self._remove_all_tags('reviewed')
        self._remove_all_tags('single')
        current_review_df = self.review_df[self.review_df[self.text_config['note_key']] == self.current_results_id]
        self.review_tag_label_dict = self.get_review_tag_label_dict(current_review_df)
        for tag_start, tag_data in self.review_tag_label_dict.iteritems():
            pos_start = '{}+{}c'.format(start, tag_data.start)
            pos_end = '{}+{}c'.format(start, tag_data.end)

            if tag_data.reviewer_labels and type(tag_data.reviewer_labels) != float:
                self.pttext.tag_add('reviewed', pos_start, pos_end)
            elif len(tag_data.annotators) == 1:
                self.pttext.tag_add('single', pos_start, pos_end)
            elif tag_data.annotator_labels.count(tag_data.annotator_labels[0]) == len(tag_data.annotator_labels):
                self.pttext.tag_add('agree', pos_start, pos_end)
            else:
                self.pttext.tag_add('disagree', pos_start, pos_end)

    def _on_review_tag_click(self, event, tag_name):
        # get the index of the mouse click
        index = event.widget.index("@%s,%s" % (event.x, event.y))
        tag_indices = list(event.widget.tag_ranges(tag_name))
        click_pos = int(self.master.call(event.widget, "count", "1.0", index))
        # iterate them pairwise (start and end index)
        for start, review_tag_data in self.review_tag_label_dict.iteritems():
            if review_tag_data.start <= click_pos <= review_tag_data.end:
                popup_menu = tk.Menu(self.master, tearoff=0)
                add_menu = tk.Menu(self.master, tearoff=0)

                popup_menu.add_command(label=review_tag_data.text, command='')
                popup_menu.add_separator()
                all_labels = []
                if review_tag_data.annotators and type(review_tag_data.annotators) != float:
                    for annotator, labels in zip(review_tag_data.annotators, review_tag_data.annotator_labels):
                        popup_menu.add_command(label=annotator + ": " + ','.join(labels), command='')
                        all_labels += labels
                if review_tag_data.reviewer_labels and type(review_tag_data.reviewer_labels) != float:
                    popup_menu.add_command(label='reviewer: ' + ','.join(review_tag_data.reviewer_labels), command='')
                    all_labels += review_tag_data.reviewer_labels
                popup_menu.add_separator()

                # Add option
                for label in self.reviewer_labels:
                    add_menu.add_command(label=label, command=lambda (start, label) = (start, label): self._add_review_tag(start, label))
                popup_menu.add_cascade(label='Add', menu=add_menu)

                # Delete option
                if tag_name == 'reviewed' or tag_name == 'agree':
                    popup_menu.add_command(label='Delete', command=lambda: self._delete_review_tag(start))
                popup_menu.tk_popup(event.x_root, event.y_root, 0)

    def _add_review_tag(self, start, label):
        # Add to reviewer column of this row. 
        row_index = self.review_df[(self.review_df[self.text_config['note_key']] == self.current_results_id) & (self.review_df['START'] == start)].index.tolist()[0]
        if type(self.review_df.at[row_index, 'REVIEWER_LABELS']) == float or not self.review_df.at[row_index, 'REVIEWER_LABELS']:
            self.review_df.at[row_index, 'REVIEWER_LABELS'] = [label]
        elif type(self.review_df.at[row_index, 'REVIEWER_LABELS']) == str:
            l = ast.literal_eval(self.review_df.at[row_index, 'REVIEWER_LABELS'])
            l.append(label)
            self.review_df.at[row_index, 'REVIEWER_LABELS'] = l
        else:
            l = self.review_df.at[row_index, 'REVIEWER_LABELS']
            self.review_df.at[row_index, 'REVIEWER_LABELS'] = l
        self.add_review_highlighting()

    def _delete_review_tag(self, start):
        self.review_df = self.review_df[~((self.review_df[self.text_config['note_key']] == self.current_results_id) \
            & (self.review_df['START'] == start))]
        self.add_review_highlighting()

    def get_review_tag_label_dict(self, current_review_df):
        review_tag_label_dict = {}
        for i, row in current_review_df.iterrows():
            annotators = row['ANNOTATORS']
            labels = row['LABELS']
            reviewer_labels = row['REVIEWER_LABELS']
            review_tag_label_dict[row['START']] = \
            ReviewTagData(row['START'], row['START'] + len(row['LABELLED_TEXT']), row['LABELLED_TEXT'], annotators, labels, reviewer_labels)
        return review_tag_label_dict

    def retrieve_label_groups(self, phrases_dict):
        endpoints = phrases_dict.keys()
        endpoints.sort()

        current_max = -1
        groups = []
        current_group = []
        for endpoint in endpoints:
            if endpoint[0] > current_max:
                current_max = endpoint[1]
                # Start a new group
                groups.append(current_group)
                current_group = [endpoint]
            else:
                current_group.append(endpoint)
                if endpoint[1] > current_max:
                    current_max = endpoint[1]
        groups.append(current_group)
        groups = groups[1:]
        new_groups = {}
        for group in groups:
            points = []
            for item in group:
                points += [item[0], item[1]]
            points = list(set(points))
            points.sort()

            for i, point in enumerate(points[:-1]):
                new_groups[(point, points[i+1])] = None

        for ngroup in new_groups.keys():
            for phrase_range, phrase_labels in phrases_dict.iteritems():
                if ngroup[0] >= phrase_range[0] and ngroup[1] <= phrase_range[1]:
                    # do not just reassign tag_data, add to existing
                    if new_groups[ngroup]:
                        new_groups[ngroup].labels += list(phrase_labels)
                        new_groups[ngroup].starts.append(phrase_range[0])
                    else:
                        new_groups[ngroup] = TagData(list(phrase_labels), [phrase_range[0]])

        return new_groups

    # first, retrieve_label_groups for each annotator
    # phrases_dicts = {annotator: {(text_start, text_end): TagData}}
    def retrieve_annotator_label_groups(self, annotator_dict):
        endpoints = []
        for ann, phrases_dict in annotator_dict.iteritems():
            endpoints += phrases_dict.keys()
        endpoints.sort()
        # Get all separate (non-overlapping) intervals
        current_max = -1
        groups = []
        current_group = []
        for endpoint in endpoints:
            if endpoint[0] > current_max:
                current_max = endpoint[1]
                # Start a new group
                groups.append(current_group)
                current_group = [endpoint]
            else:
                current_group.append(endpoint)
        groups.append(current_group)
        groups = groups[1:]

        new_groups = {}
        for group in groups:
            points = []
            for item in group:
                points += [item[0], item[1]]
            points = list(set(points))
            points.sort()
            for i, point in enumerate(points[:-1]):
                new_groups[(point, points[i+1])] = None
        # Put the correct data into the intervals
        for ann, phrases_dict in annotator_dict.iteritems():
            for phrase_range, phrase_labels in phrases_dict.iteritems():
                for group in new_groups.keys():
                    if group[0] >= phrase_range[0] and group[1] <= phrase_range[1]:
                        if new_groups[group]:
                            new_groups[group].annotator_to_labels[ann] = phrase_labels
                        else:
                            new_groups[group] = AnnotatorTagData({ann: phrase_labels}, phrase_range[0])
        return new_groups

class TagData:
    def __init__(self, labels, starts):
        self.labels = labels
        self.starts = starts

class AnnotatorTagData:
    def __init__(self, annotator_to_labels, start):
        # {annotator: labels}
        self.annotator_to_labels = annotator_to_labels
        self.start = start     

class ReviewTagData:
    def __init__(self, start, end, text, annotators, annotator_labels, reviewer_labels):
        self.start = start
        self.end = end
        self.text = text
        self.annotators = annotators
        if type(self.annotators) == str:
            self.annotators = ast.literal_eval(self.annotators)
        self.annotator_labels = annotator_labels 
        if type(self.annotator_labels) == str:
            self.annotator_labels = ast.literal_eval(self.annotator_labels)
        self.reviewer_labels = reviewer_labels
        if type(self.reviewer_labels) == str:
            self.reviewer_labels = ast.literal_eval(self.reviewer_labels)
