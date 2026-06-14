from app.models import EmailNotification
from sqlmodel import select, Session, create_engine
engine = create_engine('sqlite:///./campusflow.db')
with Session(engine) as db:
    msgs = db.exec(select(EmailNotification).where(EmailNotification.sender.like('WhatsApp:%'))).all()
    print(f'WhatsApp messages stored: {len(msgs)}')
    for m in msgs[:5]:
        print(f'  [{m.category}] {m.sender} - {m.subject[:50]}')