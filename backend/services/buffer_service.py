from database.sqlite_manager import SQLiteManager

class BufferService:
    def __init__(self):
        self.db = SQLiteManager()

    def save(self, data):
        self.db.insert(data)

    def get_all(self):
        return self.db.fetch_all()

    def delete(self, record_id):
        self.db.delete(record_id)