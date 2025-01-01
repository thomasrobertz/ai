import chromadb
from chromadb.config import Settings, DEFAULT_TENANT, DEFAULT_DATABASE
import json

chroma_client = chromadb.PersistentClient(
    path="chroma",  # Directory for storing data
    settings=Settings(),        # Default settings
    tenant=DEFAULT_TENANT,      # Default tenant
    database=DEFAULT_DATABASE   # Default database
)

collection = chroma_client.get_or_create_collection("eded")

input_file = "input/input.json"

# Read the JSON input file
with open(input_file, "r") as file:
    data = json.load(file)

# TODO Add whole file, add introductory section

# Dynamically construct metadata, skipping fields with None values
for item in data:
    metadata = {key: value for key, value in {
        "name": item["name"],
        "code": item["id"],
        "description": item["description"],
        "representation": item["representation"],
        "representation_description": item["representation_description"],
        #"representation_dict": item.get("representation_dict"),
        "note": item["note"],
        "usage": item["usage"],
        "usage_description": item["usage_description"]
    }.items() if value is not None}

    collection.add(
        documents=[item["text"]],
        ids=[item["id"]],
        metadatas=[metadata]
    )

#results = collection.query(
#    query_texts=["Query about Document identifier"],
#    n_results=2
#)
#print(results)

# Debug output
#for element in data:
#    # Access fields of each element
#    print("ID:", element["id"])
#    print("Name:", element["name"])
#    print("Description:", element["description"])
#    print("Representation:", element["representation"])
#    print("Representation Description:", element["representation_description"])
#    print("Representation Dict Type:", element["representation_dict"]["type"])
#    print("Representation Dict Max Length:", element["representation_dict"]["max_length"])
#    print("Note:", element["note"])
#    print("Usage:", element["usage"])
#    print("Usage Description:", element["usage_description"])
#    print("-" * 40)  # Separator for readability