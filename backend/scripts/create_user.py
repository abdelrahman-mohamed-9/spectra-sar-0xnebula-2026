"""Create an initial user, optionally assign an existing project role.

Run with DATABASE_URL set, after `alembic upgrade head`.
Password is prompted securely, never supplied as a CLI argument.
"""
import argparse
import getpass
from uuid import UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from spectra.core.config import get_settings
from spectra.persistence.models import User, Project, ProjectMembership
from spectra.security.auth import hash_password, normalize_email, ROLES


def main():
    parser=argparse.ArgumentParser(description='Provision SPECTRA-SAR user')
    parser.add_argument('--email',required=True)
    parser.add_argument('--project-id',type=UUID)
    parser.add_argument('--role',choices=tuple(ROLES),default='viewer')
    args=parser.parse_args()
    password=getpass.getpass('Password (12+ chars): ')
    confirmed=getpass.getpass('Confirm password: ')
    if password != confirmed: parser.error('Password confirmation mismatch')
    pw_hash=hash_password(password)
    email=normalize_email(args.email)
    db_url=get_settings().database_url
    if not db_url: parser.error('DATABASE_URL not configured')
    engine=create_engine(db_url)
    from sqlalchemy import select
    with Session(engine) as db, db.begin():
        if db.scalar(select(User.id).where(User.email==email)):
            parser.error('User already exists')
        if args.project_id and db.get(Project,args.project_id) is None:
            parser.error('Project does not exist')
        new_user=User(email=email,password_hash=pw_hash,is_active=True,is_platform_admin=False)
        db.add(new_user);db.flush()
        if args.project_id:
            db.add(ProjectMembership(user_id=new_user.id,project_id=args.project_id,role=args.role))
        print('User provisioned:',email,'id:',new_user.id)

if __name__=='__main__':main()
