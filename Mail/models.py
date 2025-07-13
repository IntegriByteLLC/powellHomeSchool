from sqlalchemy import Column, Integer, String, Boolean
from .database import Base

class ContactForm(Base):
    __tablename__ = "contact_forms"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    job_title = Column(String)
    company = Column(String)
    email = Column(String)
    phone = Column(String)
    consent = Column(Boolean, default=False)
    build_case = Column(String)
