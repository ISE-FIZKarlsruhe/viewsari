import requests
from bs4 import BeautifulSoup
import re
import json


roman2num = {"I":"0", "II":"1", "III":"2", "IV":"3", "V":"4", "VI":"5",
"VII":"6","VIII":"7","IX":"8", "X":"9"}

def parse_string(input_string):
    input_string = re.sub(";", ",",input_string)
    regex_roman = "(^.*?)((I{1,3}|I?V|V|VI{1,3}|IX|X),\s.*?$)"
    match = re.match(regex_roman, input_string)
    if match:
        if match.group(1)=="":
            name="Vasari, Giorgio, "
        else:
            name = match.group(1)
        numbers = match.group(2)
        return (name, numbers)
    else:
        return None

def scrape_index(url):

    #procedure for local file

    # Opening the html file
    HTMLFile = open("../data/html/"+url, "r")
    # # Reading the file
    index = HTMLFile.read()
    soup = BeautifulSoup(index, 'html.parser')
    # Send a GET request to the URL
    # response = requests.get(url)
    # # Parse the HTML content using Beautiful Soup
    # soup = BeautifulSoup(response.content, 'html.parser')
    #Find all unordered lists with class "none"
    ulst = soup.find('ul', {'class': 'general'})
    # Initialize an empty list to store the results
    results = []
    output = {}
    # Loop through each unordered list
    for li in ulst.find_all('li'):
        # Get the text of the list item
        text = li.get_text().strip()
        results.append(text)
    for text in results:
        text = re.sub("\n", " ", text)
        matches = parse_string(text)
        pages = []
        if matches:
            name_string = matches[0]
            numbers_string = matches[1]
            if "Life" in name_string:
                name = name_string[:-8]
            else:
                name = name_string[:-2]
            matched_nums = re.findall("(((I{1,3}|I?V|V|VI{1,3}|IX|X),\s([^\d].*?,\s)*)?\d+(\-\d+)?)",numbers_string) 
            if len(matched_nums)>0:
                try:
                    for num_list in matched_nums:
                        num_string = num_list[0]
                        if len(num_string.split(", "))>1:
                            roman = num_string.split(", ")[0]
                            decimals = num_string.split(", ")[-1]
                        else:
                            decimals = num_string
                        if "-" in decimals:
                            page_range = decimals.split("-")
                            for x in range(int(page_range[0]),int(page_range[1])+1):
                                pages.append((roman2num[roman], x))
                        else:
                            pages.append((roman2num[roman],int(decimals)))
                except Exception as e:
                    print(e)
            if len(pages)>0:
                if name in output.keys():
                    output[name].extend(pages)
                else:
                    output[name]=pages
    return output


volumes = [
    (10, "33203-h.htm")]

for idx, URL in volumes:
    output = scrape_index(url=URL)


def divide_output(dict_names, idx):
    split_output = {}
    for name, list_of_tuples in dict_names.items():
        for tup in list_of_tuples:
            if tup[0]==idx:
                if name in split_output.keys():
                    split_output[name].append(tup[1])
                else:
                    split_output[name]=[tup[1]]

    with open("../data/indices/"+idx+".json", "w", encoding="utf-8") as f:
        json.dump(split_output, f, indent=4, sort_keys=True, ensure_ascii=False)

for idx in range(10):
    divide_output(output, str(idx))