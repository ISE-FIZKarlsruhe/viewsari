import csv
import math
import glob
import sys
import re

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
    paragraph_num = 0
    name_paragraph_dict = dict()
    cooccurence_list = list()

    for file_name in sorted(glob.glob("../../data/references/*.csv")):
        with open(file_name, "r", encoding="utf-8") as f:
            data = csv.DictReader(f)
            data = list(data)
            file_num = re.match(r".*?(\d+).*?", file_name).group(1)

        print(file_num)
        paragraphs_set = set([row["paragraph"] for row in data])
        print(len(paragraphs_set))
        paragraph_num = paragraph_num + len(paragraphs_set)
        print(paragraph_num)
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


        probability_dict = dict()
        for name in name_paragraph_dict.keys():
            probability_dict[name] = name_paragraph_dict[name] / paragraph_num

        output = []
        for name1 in probability_dict.keys():
            cooccurence_dict = dict()
            for cooccurence in cooccurence_list:
                if cooccurence[0] == name1:
                    if cooccurence[1] in cooccurence_dict.keys():
                        cooccurence_dict[cooccurence[1]]["count"] += 1
                        cooccurence_dict[cooccurence[1]]["pages"].append(cooccurence[4])
                        cooccurence_dict[cooccurence[1]]["paragraphs"].append(cooccurence[3])
                        cooccurence_dict[cooccurence[1]]["volume"].append(cooccurence[2])
                        # cooccurence_dict[cooccurence[1]]["pages"] = cooccurence[4]
                        # cooccurence_dict[cooccurence[1]]["paragraphs"] = cooccurence[3]
                        # cooccurence_dict[cooccurence[1]]["volume"] = cooccurence[2]
                    else:
                        cooccurence_dict[cooccurence[1]] = {
                            "count": 1,
                            "pages": [cooccurence[4]],
                            "paragraphs": [cooccurence[3]],
                            "volume": [cooccurence[2]]
                            # "pages": cooccurence[4],
                            # "paragraphs": cooccurence[3],
                            # "volume": cooccurence[2]
                        }

            for name2, info in cooccurence_dict.items():
                p_x = probability_dict[name1]
                p_y = probability_dict[name2]
                p_yx = (info["count"] / paragraph_num) / probability_dict[name1]
                pmi_yx = math.log(p_yx / p_y, 2)
                if pmi_yx > 0:
                    output.append(
                        {
                            "x": name1,
                            "p_x": p_x,
                            "y": name2,
                            "p_y": p_y,
                            "p_yx": p_yx,
                            "pmi_yx": pmi_yx,
                            "pages": info["pages"],
                            "paragraphs": info["paragraphs"],
                            "volume": info["volume"]
                        }
                    )

        sorted_output = sorted(output, key=lambda item: float(item["pmi_yx"]), reverse=True)
        computed_pairs = set()
        new_output = []
        for x in sorted_output:
            if (x["y"], x["x"]) in computed_pairs:
                continue
            else:
                new_output.append(x)
                computed_pairs.add((x["x"], x["y"]))
        if len(new_output) > 0:
            with open("../../data/results/pmi_tables/" + file_num + ".csv", "w", encoding="utf-8") as out_f:
                csv_writer = csv.DictWriter(out_f, new_output[0].keys())
                csv_writer.writeheader()
                csv_writer.writerows(new_output)


main()
