import csv
import math
import glob
import sys
import re
import datetime

maxInt = sys.maxsize

while True:
    # decrease the maxInt value by factor 10
    # as long as the OverflowError occurs.

    try:
        csv.field_size_limit(maxInt)
        break
    except OverflowError:
        maxInt = int(maxInt / 10)


def main():
    start_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    paragraph_num = 0
    name_paragraph_dict = dict()
    cooccurence_list = list()
    dice_activity = "dice_activity_" + str(datetime.date.today())


    for file_name in sorted(glob.glob("../../data/references/*.csv")):
        with open(file_name, "r", encoding="utf-8") as f:
            data = csv.DictReader(f)
            data = list(data)
            file_num = re.match(r".*?(\d+).*?", file_name).group(1)


        paragraphs_set = set([row["paragraph"] for row in data])
        paragraph_num = paragraph_num + len(paragraphs_set)
        for paragraph in paragraphs_set:
            paragraph_data = [row for row in data if row["paragraph"] == paragraph]
            page_set = set(int(row["page"]) for row in paragraph_data)
            page = page_set.pop()
            names = list(set([row["index_name"] for row in data if
                              "|" not in row["index_name"] and row["paragraph"] == paragraph]))
            for idx in range(len(names)):
                if names[idx] in name_paragraph_dict.keys():
                    name_paragraph_dict[names[idx]] += 1
                else:
                    name_paragraph_dict[names[idx]] = 1
                for name2 in names:
                    if names[idx] != name2:
                        cooccurence_list.append((names[idx], name2, file_num, paragraph, page))

        output = []
        for name1 in name_paragraph_dict.keys():
            cooccurence_dict = {}
            for cooccurence in cooccurence_list:
                if cooccurence[0] == name1:
                    if cooccurence[1] in cooccurence_dict.keys():
                        cooccurence_dict[cooccurence[1]]["count"] += 1
                        cooccurence_dict[cooccurence[1]]["pages"].append(cooccurence[4])
                        cooccurence_dict[cooccurence[1]]["paragraphs"].append(cooccurence[3])
                        cooccurence_dict[cooccurence[1]]["volume"].append(cooccurence[2])
                    else:
                        cooccurence_dict[cooccurence[1]] = {
                            "count": 1,
                            "pages": [cooccurence[4]],
                            "paragraphs": [cooccurence[3]],
                            "volume": [cooccurence[2]],
                        }

            for name2, info in cooccurence_dict.items():
                f_x = name_paragraph_dict[name1]
                f_y = name_paragraph_dict[name2]
                f_yx = info["count"]
                dice = (2 * f_yx) / (f_x + f_y)
                output.append({
                    "artist1": name1,
                    "artist2": name2,
                    "dice_coefficient": dice,
                    "pages": info["pages"],
                    "paragraphs": info["paragraphs"],
                    "volume": info["volume"],
                    "dice_acitivty": dice_activity
                })

        sorted_output = sorted(output, key=lambda item: float(item["dice_coefficient"]), reverse=True)
        computed_pairs = set()
        new_output = []
        end_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        for x in sorted_output:
            if (x["artist2"], x["artist1"]) in computed_pairs:
                continue
            else:
                x["start"] = start_time
                x["end"] = end_time
                new_output.append(x)
                computed_pairs.add((x["artist1"], x["artist2"]))
        if len(new_output) > 0:
            with open("../../data/results/dice_tables/" + file_num + ".csv", "w", encoding="utf-8") as out_f:
                csv_writer = csv.DictWriter(out_f, new_output[0].keys())
                csv_writer.writeheader()
                csv_writer.writerows(new_output)


main()