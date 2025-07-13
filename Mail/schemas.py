from pydantic import BaseModel

class ContactFormCreate(BaseModel):
    first_name: str
    last_name: str
    job_title: str
    company: str
    email: str
    phone: str
    consent: bool
    build_case: str
