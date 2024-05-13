from tqdm import tqdm
import csv
import re
import json
from nameparser import HumanName
from transformers import BertTokenizer, BertModel
import torch
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import glob



def main():
  for file_name in glob.glob("../data/indices_raw/*.json"):
    names_data=list()
    with open(file_name, "r", encoding="utf-8") as f:
        file_data=json.load(f)
        file_num = re.match(r".*?(\d+).*?", file_name).group(1)

    for artist, pages in file_data.items():
        row = {"id":artist}
        row["middle_name"]=''
        name=row["id"]
        hbracket1=name.find('(')
        hbracket2=name.find(')')
                
        komma=name[:hbracket1].find(', ')
                
        #delete Title, because nameparser doesnt recognize it
        if hbracket1==-1:
            title=re.search('Fra|Don|Maestro',name)
            if re.search('Fran',name)!=None or (re.search('Dona',name)!=None):
                title=None
            if title!=None:
                name=name.replace(row["id"][title.start():title.end()+1],'')
                if (komma!=-1)&(name[komma:]==', '):
                    name=name.replace(', ','')       
        else:
            title=re.search('Fra|Don|Maestro',name[:hbracket1])
            if (re.search('Fran',name)!=None) or (re.search('Dona',name)!=None):
                title=None
            if title!=None:
                name=name[:hbracket1].replace(row["id"][title.start():title.end()+1],'')+name[hbracket1:hbracket2+1]
                if (komma!=-1)&(name[komma:].find(', (')!=-1):
                    name=name.replace(',','')

                

        parsed_name=HumanName(name)
        row["first_name"]=parsed_name.first
        row["surname"]=parsed_name.last
                
        #check if middle belongs to last name
        if parsed_name.middle!='':
            particle=re.search('di|da|della', parsed_name.middle)
            if particle==None:
                row["middle_name"]=parsed_name.middle
            else:
                row["surname"]=parsed_name.middle[particle.start():]+' '+row["surname"]
                if particle.start()!=0:
                    row["middle_name"]=parsed_name.middle[:particle.start()-1]

                    
        #full name
        if row["surname"]=='':
            row["full_name"]=row["first_name"]
        elif row["first_name"]=='':
            row["first_name"]=row["surname"]
            row["surname"]=''
            row["full_name"]=row["first_name"]
        elif row["middle_name"]!='':
            row["full_name"]=row["first_name"]+' '+row["middle_name"]+' '+row["surname"]
        else:
            row["full_name"]=row["first_name"]+' '+row["surname"]
        if title!=None:
            row["full_name"]=str(row["id"][title.start():title.end()]+' '+row["full_name"])
                

        #alias
        alias=parsed_name.nickname
        alias=alias.replace('called ','').replace('or ','')
        prep=re.search('\A[of|della|di|da]', alias)
                
        if prep!=None:
            row["alias"]=str(row["first_name"]+' '+alias)
        else:
            row["alias"]=alias
        if len(pages)!=0:
            row["pages"]=" ".join(sorted([str(x) for x in set(pages)]))
            keys=["id", "first_name", "middle_name", "surname", "full_name", "alias", "pages"]                    
            sorted_row={key: row[key] for key in keys}
            names_data.append(sorted_row)


    #remove dublicates
    tokenizer = BertTokenizer.from_pretrained("bert-base-multilingual-cased")
    model = BertModel.from_pretrained("bert-base-multilingual-cased")
    n=0

    for names in names_data:
      names["number"]=n
      n=n+1

    def get_wordvectors(nametype):
      print("Creating embeddings for "+nametype)
      pbar = tqdm(total=len(names_data))
      #create file of wordvectors for full_name and alias
      names_vectors=[]
      for name in names_data:
        if name[nametype]=="":
          names_vectors.append(np.zeros(768)) #if name has no alias, set wordvector to zero
          pbar.update(1)
        else:
          inputs=tokenizer(name[nametype], return_tensors="pt")
          outputs = model(**inputs) #create vectors
          last_hidden_states = outputs.last_hidden_state
          vector=last_hidden_states[0].detach().numpy() #use only the last hidden state
          length=len(vector)-2 #first and last vectors are from tokens
          
          fullname_vector=np.zeros(768)
          #average vectors
          for i in range(1,length+1,1):
            fullname_vector+=vector[i]
          fullname_vector/=length
          
          names_vectors.append(fullname_vector)
          pbar.update(1)
      return names_vectors

    for name in names_data:
      alias=name["alias"].split(", ")
      name["alias1"]=alias[0]
      if len(alias)>1:
        name["alias2"]=alias[1]
      else:
        name["alias2"]=""
    fullnames=get_wordvectors("full_name")
    alias1=get_wordvectors("alias1")
    alias2=get_wordvectors("alias2")

    fullnames_similarity=cosine_similarity(fullnames)
    alias1_similarity=cosine_similarity(alias1)
    alias2_similarity=cosine_similarity(alias2)
    mixed_similarity1=cosine_similarity(fullnames, alias1)
    mixed_similarity2=cosine_similarity(fullnames, alias2)
    mixed_similarity3=cosine_similarity(alias1, alias2)

    i=0

    for name1 in names_data:
      s=i+1
      num1=name1["number"]
      for name2 in names_data[i+1:]:
        if (name1["pages"]==name2["pages"])&(name1["pages"]!=""):
          num2=name2["number"]
          similarities= [fullnames_similarity[num1,num2], alias1_similarity[num1,num2], alias2_similarity[num1,num2], mixed_similarity1[num1,num2], mixed_similarity1[num2,num1], mixed_similarity2[num1,num2], mixed_similarity2[num2,num1], mixed_similarity3[num1,num2], mixed_similarity3[num2,num1]]
          max_similarity=max(similarities)
          if (max_similarity>0.9):
            #treshold 0.9
            name_var1=[name1["full_name"]]
            name_var1.extend(name1["alias"].split(", "))
            name_var1 = [name for name in name_var1 if len(name)>0]
            name_var2=[name2["full_name"]]
            name_var2.extend(name2["alias"].split(", "))
            name_var2 = [name for name in name_var2 if len(name)>0]
            for name in name_var2:
              if (name in name_var1)==False:
                name1["alias"]=name1["alias"]+", "+name
            names_data.pop(s)
          
            s=s-1
            
          elif (max_similarity>0.8)&(max_similarity<=0.9):
            #check names close to treshold
            if name1["first_name"]==name2["first_name"]:
              name_var1=[name1["full_name"]]
              name_var1.extend(name1["alias"].split(", "))
              name_var1 = [name for name in name_var1 if len(name)>0]
              name_var2=[name2["full_name"]]
              name_var2.extend(name2["alias"].split(", "))
              name_var2 = [name for name in name_var2 if len(name)>0]
              for name in name_var2:
                if (name in name_var1)==False:
                  name1["alias"]=name1["alias"]+", "+name
              names_data.pop(s)
              
              s=s-1
        s=s+1
      i=i+1

    for name in names_data:
        name.pop("alias1")
        name.pop("alias2")
        name.pop("number")
    with open('../results/indices_parsed/'+file_num+'.csv', 'w', encoding="utf-8") as file:
        csv_writer=csv.DictWriter(file, fieldnames=["id","first_name", "middle_name", "surname", "full_name", "alias", "pages"])
        csv_writer.writeheader()
        csv_writer.writerows(names_data)

main()