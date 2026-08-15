"""
Unit tests for app.auth.service — business logic only, no HTTP layer.
"""
import pytest

from app.auth.service import AuthError, authenticate_user, register_user
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.schemas.auth import UserLogin, UserRegister
from app.tests.conftest import unique_email


def test_register_user_creates_user_and_personal_org(db_session, seeded_roles):
    payload = UserRegister(
        email=unique_email(),
        password="supersecret123",
        full_name="Jane Doe",
        organization_name="Jane's Agency",
    )
    user = register_user(db_session, payload)

    assert user.id is not None
    assert user.email == payload.email
    assert user.hashed_password != payload.password  # never stored plaintext

    org = db_session.query(Organization).filter(Organization.name == "Jane's Agency").first()
    assert org is not None
    assert org.slug == "jane-s-agency"

    membership = (
        db_session.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user.id, OrganizationMember.organization_id == org.id)
        .first()
    )
    assert membership is not None
    assert membership.role.name == "owner"


def test_register_user_rejects_duplicate_email(db_session, seeded_roles):
    email = unique_email()
    payload = UserRegister(
        email=email, password="supersecret123", full_name="First", organization_name="Org One"
    )
    register_user(db_session, payload)

    dup_payload = UserRegister(
        email=email, password="anotherpassword", full_name="Second", organization_name="Org Two"
    )
    with pytest.raises(AuthError):
        register_user(db_session, dup_payload)


def test_register_user_handles_slug_collision(db_session, seeded_roles):
    payload_a = UserRegister(
        email=unique_email(), password="supersecret123", full_name="A", organization_name="Acme"
    )
    register_user(db_session, payload_a)

    payload_b = UserRegister(
        email=unique_email(), password="supersecret123", full_name="B", organization_name="Acme"
    )
    user_b = register_user(db_session, payload_b)

    orgs = (
        db_session.query(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .filter(OrganizationMember.user_id == user_b.id)
        .all()
    )
    assert orgs[0].slug == "acme-2"


def test_register_user_without_seeded_roles_raises(db_session):
    payload = UserRegister(
        email=unique_email(), password="supersecret123", full_name="X", organization_name="Org"
    )
    with pytest.raises(AuthError):
        register_user(db_session, payload)


def test_authenticate_user_succeeds_with_correct_password(db_session, seeded_roles):
    email = unique_email()
    register_user(
        db_session,
        UserRegister(email=email, password="correct-password", full_name="A", organization_name="Org"),
    )
    user = authenticate_user(db_session, UserLogin(email=email, password="correct-password"))
    assert user.email == email


def test_authenticate_user_rejects_wrong_password(db_session, seeded_roles):
    email = unique_email()
    register_user(
        db_session,
        UserRegister(email=email, password="correct-password", full_name="A", organization_name="Org"),
    )
    with pytest.raises(AuthError):
        authenticate_user(db_session, UserLogin(email=email, password="wrong-password"))


def test_authenticate_user_rejects_unknown_email(db_session):
    with pytest.raises(AuthError):
        authenticate_user(db_session, UserLogin(email="nobody@example.com", password="whatever123"))


def test_authenticate_user_rejects_inactive_account(db_session, seeded_roles):
    email = unique_email()
    user = register_user(
        db_session,
        UserRegister(email=email, password="correct-password", full_name="A", organization_name="Org"),
    )
    user.is_active = False
    db_session.commit()

    with pytest.raises(AuthError):
        authenticate_user(db_session, UserLogin(email=email, password="correct-password"))
