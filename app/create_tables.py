from app.core.database import engine
from app.models.user import User
from app.core.database import Base

Base.metadata.create_all(bind=engine)
print("✅ Tables created successfully")
