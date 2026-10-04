from sqlalchemy import Column, Integer, String, JSON
from .database import Base

class Drug(Base):
    __tablename__ = "drugs"

    id = Column(Integer, primary_key=True, index=True)
    trade_en = Column(String, index=True)
    trade_ar = Column(String, index=True, nullable=True)
    generic_en = Column(String, index=True, nullable=True)
    generic_ar = Column(String, nullable=True)
    form = Column(String, index=True, nullable=True)
    form_ar = Column(String, nullable=True)
    strength = Column(String, nullable=True)
    cls = Column(String, index=True, nullable=True)
    indications = Column(String, nullable=True)
    dosage = Column(String, nullable=True)
    side_effects = Column(String, nullable=True)
    contraindications = Column(String, nullable=True)
    pregnancy = Column(String, nullable=True)

    # Store alternates as a JSON array natively. In Postgres this could be ARRAY(String).
    alternates = Column(JSON, nullable=True, default=list)
