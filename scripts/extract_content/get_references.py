import csv
from pathlib import Path

from fastcoref import LingMessCoref
import glob
import sys
import re
import pandas as pd

maxInt = sys.maxsize

while True:
    # decrease the maxInt value by factor 10 
    # as long as the OverflowError occurs.
    try:
        csv.field_size_limit(maxInt)
        break
    except OverflowError:
        maxInt = int(maxInt / 10)

print("Start, loading model!")
model = LingMessCoref(device='cuda:0')


def main():
    for file_name in glob.glob("../../data/volumes_updated/*.csv"):
        print(f"Working on {file_name}.")
        file_num = re.match(r".*?(\d+).*?", file_name).group(1)
        text_data = pd.read_csv(file_name)
        output = []

        with open(f"../../data/indices_parsed/{file_num}.csv", "r") as f:
            names_data = csv.DictReader(f)
            names_data = list(names_data)

        for index, row in text_data.iterrows():
            page_num = row['page']
            paragraph_num = row['paragraph_id']
            page_text = row['text']
            if pd.isna(page_text):
                page_text = ""

            names_on_page = [name for name in names_data if str(page_num) in name["pages"].split(" ")]

            preds = model.predict(texts=[page_text])
            if len(preds) > 0:
                characters = preds[0].get_clusters(as_strings=False)
                clusters = preds[0].get_clusters()
                for surfaces, char_pos in zip(clusters, characters):
                    references = [surface.lower() for surface in surfaces]
                    name_id = []
                    max_matches = 0
                    max_tokens_matched = 0
                    for name in names_on_page:
                        num_matches = 0
                        num_tokens_matched = 0
                        name_var = [name["first_name"].lower(), name["surname"].lower(), name["full_name"].lower()]
                        name_var.extend(name["alias"].lower().split(", "))
                        name_var = set([name for name in name_var if len(name) > 0])
                        if len(name_var.intersection(set(references))) > 0:
                            for variant in name_var:
                                if variant in references:
                                    num_matches += len([x for x in references if x == variant])
                                    if len(variant.split(" ")) > num_tokens_matched:
                                        num_tokens_matched = len(variant.split(" "))
                            if num_matches > max_matches:
                                name_id = [name["id"]]
                                max_matches = num_matches
                                max_tokens_matched = num_tokens_matched
                            elif num_matches == max_matches and num_tokens_matched > max_tokens_matched:
                                name_id = [name["id"]]
                                max_tokens_matched = num_tokens_matched
                            elif num_matches == max_matches:
                                name_id.append(name["id"])
                    if len(name_id) > 0:
                        text_length = 0
                        name_id = "|".join(name_id)
                        for i in range(len(surfaces)):
                            curr_paragraph = paragraph_num
                            print(f"Current paragraph: {curr_paragraph}.")
                            output.append([page_num, name_id, char_pos[i], surfaces[i], curr_paragraph])

        with open(f"../../data/references/{Path(file_name).stem}_v1.csv", "w", encoding="utf-8") as file:
            writer = csv.writer(file, delimiter=",")
            writer.writerow(["page", "index_name", "position", "reference", "paragraph"])
            writer.writerows(output)


main()
