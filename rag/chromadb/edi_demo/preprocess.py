import re
import json

USAGE_DICT = {
    "[B]": "used in batch messages only",
    "[I]": "used in interactive messages only",
    "[C]": "common usage in both batch and interactive messages"
}

REPR_DICT = {
    "a": "alphabetic",
    "n": "numeric",
    "an": "alphanumeric"
}

def parseRepr(repr):
    prepr = ""
    chars = "characters"
    type = ""
    max = ""

    if (".." in repr):
        prepr = "Up to "

    v_pattern = r"(\d+)"
    an_pattern = r"([a|n|an]+)"

    v_match = re.search(v_pattern, repr)
    an_match = re.search(an_pattern, repr)

    if v_match:
        max = v_match.group(1)
        prepr += max + " "
        if max == "1":
            chars = "character"

    if an_match:
        type = REPR_DICT[an_match.group(1)] 
        prepr += type + " "

    return prepr + chars, type, max

def read():
    with open('input/eded.txt', 'r') as file:
        file_content = file.read()
        
        sections = re.split(r'^-{10,}', file_content, flags=re.MULTILINE)
        introduction = sections[:1]
        rag_input = []
        id_pattern = r"^(\d+)"
        usage_pattern = r"(\[[B|I|C]\])$"

        for i, section in enumerate(sections[1:]):
            #print(section)
            sectionLines = [line for line in section.strip().split('\n') if line.strip()]
            id=""
            name=""
            desc=""
            note=""  
            repr=""
            repr_desc=""
            repr_type=""
            repr_max=""
            usage=""
            usage_desc=""

            for index, line in enumerate(sectionLines):
                
                id_match = re.search(id_pattern, line)

                if id_match:
                    id = id_match.group(1).strip()
                    line = re.sub(id, "", line).strip()
                    usage_match = re.search(usage_pattern, line)
                    if usage_match:
                        usage = usage_match.group(1)
                        usage_desc = USAGE_DICT[usage]
                        line = line.replace(usage, "").strip()
                    name = line.strip()

                if "Desc:" in line:
                    desc = line.split(":")[1].strip()
                
                if "Repr:" in line:
                    repr = line.split(":")[1].strip()
                    prepr, repr_type, repr_max = parseRepr(repr)

                if "Note:" in line:
                    for x in range(index + 1, len(sectionLines)):
                        noteLine = sectionLines[x].strip()
                        noteLine = re.sub(r"^\s?1\s", "", noteLine).strip()
                        note = (note + " " + noteLine).strip()

            text = "[Code:] " + id
            text += "\n[Name:] " + name.replace('.', '')
            text += "\n[Description:] " + desc.replace('.', '')
            text += "\n[Representation:] " + repr

            if note:  
                text += f"\n[Note:] {note}"

            final_note = None if not note else note

            rag_input.append({
                "id": id,
                "text": text,
                "name": name,
                "description": desc,
                "representation": repr,
                "representation_description": prepr,
                # These might introduce unwanted redundancy
                #"representation_dict": {
                #    "type": repr_type, "max_length": repr_max
                #},
                "note": final_note,  
                "usage": usage,
                "usage_description": usage_desc
            })

        write(rag_input)

def write(rag_input):
    output_file = "input/input.json"
    with open(output_file, "w") as file:
        json.dump(rag_input, file, indent=4) 

read()
