from typing import Optional, List

from fastapi import HTTPException
from sqlalchemy import func, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette import status

from api.password import verify_password, hash_password
from api.verifyModel import UserOut, UserCreate, UserInDB, Userbase, UpdateSuccess, PubUserInfo, UploadSuccess, \
    PostInDB, ANewTag, PostOut
from sql.dbModels import User, Post, Tag, PostTag


async def findUser_by_name(session: AsyncSession, username: str) -> UserOut | None:
    r = await session.execute(select(User).where(User.username == username))
    user: User | None = r.scalar_one_or_none()
    if user is not None:
        return UserOut(
            id=user.id,
            username=user.username,
            avatar=user.avatar,
            group_id=user.group_id,
            state=user.state,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    else:
        return None


async def findPubUser_by_name(session: AsyncSession, username: str) -> PubUserInfo | None:
    r = await session.execute(select(User).where(User.username == username))
    user: User | None = r.scalar_one_or_none()
    if user is not None:
        return PubUserInfo(
            username=user.username,
            avatar=user.avatar,
            state=user.state
        )
    else:
        return None


async def get_user(session: AsyncSession, username: str) -> UserInDB | None:
    r = await session.execute(select(User).where(User.username == username))
    user: User | None = r.scalar_one_or_none()
    if user is not None:
        return UserInDB(
            id=user.id,
            username=user.username,
            password=user.password,
            avatar=user.avatar,
            group_id=user.group_id,
            state=user.state,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    else:
        return None


async def check_passwd(session: AsyncSession, username: str, password: str) -> bool:
    r = await session.execute(select(User).where(User.username == username))
    user: User | None = r.scalar_one_or_none()
    if user is None:
        return False
    if verify_password(password, user.password) is True:
        return True


async def create_user(session: AsyncSession, usercreate: UserCreate):
    usercreate.password = hash_password(usercreate.password)
    try:
        session.add(User(
            username=usercreate.username,
            password=usercreate.password,
            avatar='default.jpg')
        )
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "Duplicate entry" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='用户名已经被注册')


async def change_user_name(session: AsyncSession, user_old: Userbase, username_new: str) -> UserOut:
    if check_passwd(session, user_old.username, user_old.password) is True:
        try:
            r = await session.execute(select(User).where(User.username == user_old.username))
            user = r.scalars().first()
            if user:
                user.username = username_new
                user.updated_at = func.now()
                await session.commit()
            u = (await session.execute(select(User).where(User.username == username_new))).first()
            assert u is not None
            return UpdateSuccess.from_User(u, "更新成功")
        except IntegrityError as e:
            await session.rollback()
            if "Duplicate entry" in str(e):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='该用户名已经存在')
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="未知错误" + str(e))
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='用户名或密码错误')


async def change_user_passwd(session: AsyncSession, user_old: Userbase, password_new: str, ) -> UserOut:
    if check_passwd(session, user_old.username, user_old.password) is True:
        try:
            r = await session.execute(select(User).where(User.username == user_old.username))
            user = r.scalars().first()
            if user:
                user.password = hash_password(password_new)
                user.updated_at = func.now()
                await session.commit()
            u = (await session.execute(select(User).where(User.username == user_old.username))).first()
            assert u is not None
            return UpdateSuccess.from_User(u, "更新成功")
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="未知错误" + str(e))
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='用户名或密码错误')


async def change_user_avatar(session: AsyncSession, username: str, fileinfo: UploadSuccess) -> UploadSuccess:
    try:
        r = await session.execute(select(User).where(User.username == username))
        user = r.scalars().first()
        if user:
            user.avatar = fileinfo.filename
            user.updated_at = func.now()
            await session.commit()
        return UploadSuccess(filename=fileinfo.filename, content_type=fileinfo.content_type, detail=fileinfo.detail)
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="未知错误" + str(e))


async def get_all_user(session: AsyncSession) -> list[UserOut | None]:
    r = await session.execute(select(User).where(User.group_id == 0))
    users = r.scalars().all()
    return [UserOut(
        id=user.id,
        username=user.username,
        avatar=user.avatar,
        group_id=user.group_id,
        state=user.state,
        created_at=user.created_at,
        updated_at=user.updated_at
    ) for user in users]


async def delete_user(session: AsyncSession, username: str):
    try:
        r = await session.execute(select(User).where(User.username == username))
        user = r.scalars().first()
        if user is not None:
            # 删除该用户相关的所有文章的PostTag映射
            await session.execute(
                delete(PostTag).where(PostTag.post_id.in_(
                    select(Post.id).where(Post.user_id == user.id)
                ))
            )
            await updateTagCount(session)
            # 删除该用户相关的所有文章
            await session.execute(delete(Post).where(Post.user_id == user.id))
            await session.delete(user)
            await session.commit()
            return {"detail": "删除成功"}
        else:
            return {"detail": "用户不存在，删除失败"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='未知错误' + str(e))


# -------------------------------------------------------------------post
async def updateTagCount(session: AsyncSession):
    try:
        tags = await session.execute(select(Tag))
        tags = tags.all()
        for tag in tags:
            tag_id: int = tag[0].id
            count = await session.execute(select(PostTag).where(PostTag.tag_id == tag_id))
            count = len(count.all())
            tag = (await session.execute(select(Tag).where(Tag.id == tag_id))).scalar_one()
            tag.reference_count = count
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='更新tag计数失败' + str(e))


async def new_post(session: AsyncSession, a_post: PostInDB) -> PostOut:
    try:
        # 查询指定用户名的用户
        user = await session.execute(select(User).where(User.username == a_post.username))
        user = user.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="your username not found, cannot new post")
        # 创建新的文章
        post = Post(title=a_post.title, content=a_post.content, user_id=user.id)
        session.add(post)
        await session.commit()
        if a_post.tag_names is not []:
            tags = []
            for tag_name in a_post.tag_names:
                tag = await session.execute(select(Tag).where(Tag.name == tag_name))
                tag = tag.scalar_one_or_none()
                if tag is None:
                    tag = Tag(name=tag_name)
                    session.add(tag)
                tags.append(tag)
            # 将标签和文章关联起来
            await session.commit()
            for tag in tags:
                post_tag = PostTag(post_id=post.id, tag_id=tag.id)
                session.add(post_tag)
            await session.commit()
        await updateTagCount(session)
        return await get_post_ById(session, post.id)
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


async def get_post_ById(session: AsyncSession, post_id: int) -> Optional[PostOut]:
    post = await session.execute(select(Post).where(Post.id == post_id))
    post = post.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    user = await get_post_owner(session, post.user_id)
    post_out = PostOut(
        id=post.id,
        user_id=post.user_id,
        author=user.username,
        author_img=user.avatar,
        title=post.title,
        content=post.content,
        tags=await get_post_tag(session, post.id),
        state=post.state,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )
    return post_out


async def get_post_tag(session: AsyncSession, pid: int) -> list[Optional[str]]:
    a = await session.execute(select(Tag.name).join(PostTag).filter(PostTag.post_id == pid))
    return [tag[0] for tag in a.all()]


async def get_post_owner(session: AsyncSession, uid: int) -> User:
    u = await session.execute(select(User).where(User.id == uid))
    return u.scalar_one_or_none()


async def get_all_posts_ByPage(session: AsyncSession, page: int, pagesize: int) -> List[Optional[PostOut]]:
    try:
        offset = (page - 1) * pagesize
        posts = await session.execute(select(Post).offset(offset).limit(pagesize))
        post_list = posts.scalars().all()
        if post_list is None:
            return []
        post_out_list = []
        for post in post_list:
            user = await get_post_owner(session, post.user_id)
            post_out = PostOut(
                id=post.id,
                user_id=post.user_id,
                author=user.username,
                author_img=user.avatar,
                title=post.title,
                content=str(post.content)[:200],
                tags=await get_post_tag(session, post.id),
                state=post.state,
                created_at=post.created_at,
                updated_at=post.updated_at,
            )
            post_out_list.append(post_out)
        return post_out_list
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def get_user_posts_ByPage(session: AsyncSession, username: str, page: int, pagesize: int) -> List[PostOut]:
    offset = (page - 1) * pagesize
    user = await get_user(session, username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='user not found')
    posts = await session.execute(select(Post).
                                  where(Post.user_id == user.id)
                                  .offset(offset).limit(pagesize))
    post_list = posts.scalars().all()
    post_out_list = []
    for post in post_list:
        user = await get_post_owner(session, post.user_id)
        post_out = PostOut(
            id=post.id,
            user_id=post.user_id,
            author=user.username,
            author_img=user.avatar,
            title=post.title,
            content=str(post.content)[:200],
            tags=await get_post_tag(session, post.id),
            state=post.state,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )
        post_out_list.append(post_out)
    return post_out_list


async def get_user_all_tags(session: AsyncSession, username: str) -> List[str]:
    tags = await session.execute(select(Tag.name)
                                 .join(PostTag, PostTag.tag_id == Tag.id)
                                 .join(Post, PostTag.post_id == Post.id)
                                 .where(Post.id.in_(select(Post.id)
                                                    .join(User).where(User.username == username)
                                                    .subquery().select())
                                        ).distinct())
    tag_list = [tag[0] for tag in tags.all()]
    return tag_list


async def update_post_authorized(session: AsyncSession, post_id: int, title: str, content: str, username: str) -> str:
    try:
        post = await session.execute(select(Post).where(Post.id == post_id))
        post = post.scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=404, detail="Post not found")
        uid: int = post.user_id
        author = await session.execute(select(User.username).where(User.id == uid))
        author = author.first()[0]
        if author != username:
            raise HTTPException(status_code=403,
                                detail=f"You are not authorized to update this post, this post belong to {author}")
        post.title = title
        post.content = content
        post.updated_at = func.now()
        await session.commit()
        return '更新成功'
    except Exception as e:
        await session.rollback()
        # raise e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='更新post失败,' + str(e))


async def delete_post(session: AsyncSession, post_id: int, username: str) -> str:
    try:
        post = await session.execute(select(Post).where(Post.id == post_id))
        post = post.scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=404, detail="Post not found")
        user = await get_user(session, username)
        if user.id != post.user_id:
            raise HTTPException(status_code=401, detail=f"You are not authorized to delete this post,"
                                                        f" this post belong to {user.username}")
        # 删除对应postTag
        await session.execute(delete(PostTag).where(PostTag.post_id == post_id))
        await updateTagCount(session)
        await session.delete(post)
        await session.commit()
        return '删除成功'
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='删除post失败,' + str(e))


async def new_tag(session: AsyncSession, a_tag: ANewTag):
    try:
        tag = Tag(name=a_tag.name)
        session.add(tag)
        await session.commit()
        return tag
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


async def del_tag(session: AsyncSession, tag_id: int):
    try:
        await updateTagCount(session)
        t = await session.execute(select(Tag).where(Tag.id == tag_id))
        t = t.scalar_one_or_none()
        if t is None:
            raise HTTPException(status_code=404, detail='tag not found')
        if t.reference_count > 0:
            raise HTTPException(status_code=400, detail=f'have {t.reference_count} post used this tag, cannot del')
        await session.execute(delete(Tag).where(Tag.id == tag_id))
        await session.commit()
        return '删除成功'
    except Exception as e:
        await session.rollback()
        # raise e
        raise HTTPException(status_code=400, detail=str('删除失败'))


async def get_all_tags(session: AsyncSession):
    try:
        await updateTagCount(session)
        tags = await session.execute(select(Tag))
        tags = tags.scalars().all()
        return tags
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


async def add_tag_to_post_authorized(session: AsyncSession, post_id: int, tag_name: str,
                                     username: str) -> str:
    try:
        post = await session.execute(select(Post).where(Post.id == post_id))
        post = post.scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=404, detail="Post not found")
        user = await get_user(session, username)
        if user.id != post.user_id:
            raise HTTPException(status_code=401, detail=f"You are not authorized,"
                                                        f" this post belong to {user.username}")
        tag = await session.execute(select(Tag).where(Tag.name == tag_name))
        tag = tag.scalar_one_or_none()
        if tag is None:
            tag = Tag(name=tag_name)
            session.add(tag)
        await session.commit()
        post_tag = PostTag(post_id=post.id, tag_id=tag.id)
        session.add(post_tag)
        await session.commit()
        await updateTagCount(session)
        return '更新成功'
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='更新失败' + str(e))


async def get_posts_ByTagPage(session: AsyncSession, tag_name: str, page: int, pagesize: int) -> list[PostOut]:
    offset = (page - 1) * pagesize
    posts = await session.execute(select(Post).join(PostTag).join(Tag)
                                  .filter(Tag.name == tag_name).offset(offset).limit(pagesize))
    posts = posts.scalars()
    post_out_list = []
    for post in posts:
        po = await get_post_ById(session, post_id=post.id)
        po.content = str(po.content)[:200]
        post_out_list.append(po)
    return post_out_list


if __name__ == '__main__':
    ...
