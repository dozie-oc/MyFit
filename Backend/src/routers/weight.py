from fastapi import APIRouter, status
from sqlmodel import select

from src.dependencies import CurrentUserDep, SessionDep
from src.models import User, WeightLog
from src.schemas import WeightLogCreate, WeightLogOut


router = APIRouter(
    prefix="/weight",
    tags=["Weight"]
)


@router.post(
    "",
    response_model=WeightLogOut,
    status_code=status.HTTP_201_CREATED
)
def create_weight_log(
    weight_data: WeightLogCreate,
    session: SessionDep,
    current_user: CurrentUserDep
):

    weight_log = WeightLog(
        user_id=current_user.id,
        date=weight_data.date,
        weight=weight_data.weight
    )

    session.add(weight_log)

    # Keep User.weight as the latest known weight.
    current_user.weight = weight_data.weight

    session.add(current_user)

    session.commit()
    session.refresh(weight_log)

    return weight_log


@router.get(
    "",
    response_model=list[WeightLogOut]
)
def get_weight_logs(
    session: SessionDep,
    current_user: CurrentUserDep
):

    logs = session.exec(
        select(WeightLog).where(
            WeightLog.user_id == current_user.id
        ).order_by(
            WeightLog.date.desc()
        )
    ).all()

    return logs