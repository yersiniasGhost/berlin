import json
from pathlib import Path
from pymongo import MongoClient
from bson import ObjectId


class Profile:
    def __init__(self, sections):
        self.sections = sections
        print(f"Profile initialized with sections: {self.sections}")  # Debug print

    def get_sections(self):
        return self.sections

    def number_of_sections(self):
        return len(self.sections)

    @classmethod
    def from_json(cls, path: Path) -> "Profile":
        if not path.exists():
            raise ValueError(f'Path does not exist: {path}')
        with open(path, 'r') as file:
            profile_definition = json.load(file)
            return Profile(profile_definition)

    @classmethod
    def from_mongodb(cls, document_id):
        client = MongoClient("mongodb://localhost:27017/")
        db = client['MTA_devel']
        collection = db['Profiles']

        document = collection.find_one({"_id": ObjectId(document_id)})
        if not document:
            raise ValueError(f"Document with id {document_id} not found")

        definition = document.get('definition')
        if not definition:
            raise ValueError(f"No definition in {document_id}")

        print(f"Retrieved definition from MongoDB: {definition}")
        return cls(definition)

    # we may never do this, or we might
    # write storage and retrival to/from Mongo