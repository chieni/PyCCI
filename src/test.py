import pandas as pd
#phrases_dict = {(329, 341): ['LIM', 'FAM'], (339, 350):['CAR'], (450, 530):['FAM'], (521, 640):['CAR'], (1525, 1910):['CAR'], (2054, 2063):['CAR'], (2164, 2169):['LIM']}
import re

class TagData:
    def __init__(self, labels, start):
        self.labels = labels
        self.start = start

    def __eq__(self, other):
        if set(self.labels) == set(other.labels) and self.start == other.start:
            return True
        return False

class AnnotatorTagData:
    def __init__(self, annotator_to_labels, start):
        # {annotator: labels}
        self.annotator_to_labels = annotator_to_labels
        self.start = start        

def _clean_text(text):
    if type(text) == float:
        return text
    cleaned = str(text.replace('\r\r', '\n').replace('\r', ''))
    cleaned = re.sub(r'\n+', '\n', cleaned)
    cleaned = re.sub(r' +', ' ', cleaned)
    cleaned = re.sub(r'\t', ' ', cleaned)
    return str(cleaned.strip())

def retrieve_label_groups(phrases_dict):
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
    groups.append(current_group)
    groups = groups[1:]

    new_groups = {}
    for group in groups:
        points = []
        for item in group:
            points += [item[0], item[1]]
        points.sort()
        for i, point in enumerate(points[:-1]):
            new_groups[(point, points[i+1])] = None

    for phrase_range, phrase_labels in phrases_dict.iteritems():
        for group in new_groups.keys():
            if group[0] >= phrase_range[0] and group[1] <= phrase_range[1]:
                new_groups[group] = TagData(phrase_labels, phrase_range[0])

    return new_groups

# first, retrieve_label_groups for each annotator
# phrases_dicts = {annotator: {(text_start, text_end): TagData}}
def retrieve_annotator_label_groups(annotator_dict):
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

def create_review_dict_for_note(current_note_id, comparison_dfs):
    current_note_text = None
    annotator_dict = {}
    for i, df in enumerate(comparison_dfs):
        current_results_df = df[(df['ROW_ID'] == current_note_id) & (df['NO_LABELS'] == 0)]
        phrases_dict = {}
        for j, row in current_results_df.iterrows():
            current_note_text = row['TEXT']
            text_start = int(row['START'])
            text_end = int(row['START'] + len(row['LABELLED_TEXT']))
            current_label = row['LABEL']
            if (text_start, text_end) in phrases_dict:
                phrases_dict[(text_start, text_end)].append(current_label)
            else:
                phrases_dict[(text_start, text_end)] = [current_label]
        annotator_dict['annotator' + str(i)] = retrieve_label_groups(phrases_dict)

    #ROW_ID, TEXT, LABELLED_TEXT, LABELs, ANNOTATORS, REVIEWER_LABELS
    reviewer_dicts = []
    for interval, ann_tag_data in retrieve_annotator_label_groups(annotator_dict).iteritems():
        labels = []
        annotators = []
        for key, val in ann_tag_data.annotator_to_labels.iteritems():
            annotators.append(key)
            labels.append(val.labels)
        reviewer_dict = {
        'ROW_ID': current_note_id,
        'TEXT': current_note_text,
        'LABELLED_TEXT': current_note_text[interval[0]:interval[1]],
        'START': interval[0],
        'LABELS': labels,
        'ANNOTATORS': annotators,
        'REVIEWER_LABELS': None
        }
        reviewer_dicts.append(reviewer_dict)
    return reviewer_dicts

directory = '~/Documents/hf_symptoms/data/data_annotated/'
review_fname = directory + 'df_500Results_reviewed.csv'
comparison_files = [directory + 'df_500Results_miryam.csv', directory + 'df_500Results_ashwin.csv']
comparison_dfs = []
review_row_ids = []
reviewer_dicts = []

for fname in comparison_files:
    df = pd.read_csv(fname, index_col=0, header=0)
    df['TEXT'] = df['TEXT'].map(lambda text: _clean_text(text))
    comparison_dfs.append(df)

for df in comparison_dfs:
    review_row_ids += df['ROW_ID'].unique().tolist()

# review_row_ids = review_row_ids[:3]
for row_id in review_row_ids:
    reviewer_dicts += create_review_dict_for_note(row_id, comparison_dfs)

pd.DataFrame(reviewer_dicts).to_csv(review_fname)
    



