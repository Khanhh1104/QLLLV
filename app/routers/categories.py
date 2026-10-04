from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/categories", tags=["Danh mục"])


@router.get("", response_model=list[schemas.CategoryOut])
def categories(
    db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)
):
    return (
        db.query(models.Category)
        .filter_by(owner_id=user.id)
        .order_by(models.Category.name)
        .all()
    )


def save(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Tên danh mục đã tồn tại")


@router.post("", response_model=schemas.CategoryOut, status_code=201)
def create(
    data: schemas.CategoryIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    category = models.Category(**data.model_dump(), owner_id=user.id)
    db.add(category)
    save(db)
    db.refresh(category)
    return category


@router.put("/{category_id}", response_model=schemas.CategoryOut)
def update(
    category_id: int,
    data: schemas.CategoryIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    category = (
        db.query(models.Category).filter_by(id=category_id, owner_id=user.id).first()
    )
    if not category:
        raise HTTPException(404, "Không tìm thấy danh mục")
    db.query(models.Task).filter_by(owner_id=user.id, category=category.name).update(
        {"category": data.name}
    )
    category.name = data.name
    category.color = data.color
    save(db)
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
def delete(
    category_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    category = (
        db.query(models.Category).filter_by(id=category_id, owner_id=user.id).first()
    )
    if not category:
        raise HTTPException(404, "Không tìm thấy danh mục")
    db.query(models.Task).filter_by(owner_id=user.id, category=category.name).update(
        {"category": None}
    )
    db.delete(category)
    db.commit()
