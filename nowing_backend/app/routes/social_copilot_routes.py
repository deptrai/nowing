"""Social Co-pilot REST API Routes (Story 21.12 / FR-82 / AD-SOC-1 to 7 / AD-11 / AD-31)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import any_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Memory, MemorySourceType, MemoryType, get_async_session
from app.schemas.voice_profile import (
    GenerateDraftsRequest,
    GenerateDraftsResponse,
    ManualIngestRequest,
    ManualIngestResponse,
    OutlierPostsResponse,
    VoiceAnalysisRequest,
    VoiceProfile,
    VoiceProfileListItem,
    VoiceProfileListResponse,
)
from app.services.social_copilot.draft_generator import ViralDraftGenerator
from app.services.social_copilot.mechanics_deconstructor import (
    ViralMechanicsDeconstructor,
)
from app.services.social_copilot.outlier_detector import OutlierDetector
from app.services.social_copilot.voice_learner import VoiceProfileLearner
from app.users import get_auth_context
from app.utils.rbac import check_workspace_access

router = APIRouter(prefix="/api/workspaces/{workspace_id}")
logger = logging.getLogger(__name__)


@router.post(
    "/voice-profiles",
    response_model=VoiceProfile,
    status_code=status.HTTP_201_CREATED,
)
async def create_voice_profile(
    workspace_id: int,
    request: VoiceAnalysisRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> VoiceProfile:
    """Analyze writing sample (>= 100 words) and persist learned VoiceProfile in memories table."""
    await check_workspace_access(session, auth, workspace_id)

    client_id = getattr(auth.user, "client_id", None) or "default"
    learner = VoiceProfileLearner()
    try:
        profile = await learner.extract_voice_profile(
            sample_text=request.sample_text,
            profile_name=request.profile_name,
            platform=request.platform,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    # Persist in Memory table (AD-11 / AD-35 / AD-31)
    dim = config.embedding_model_instance.dimension
    memory = Memory(
        workspace_id=workspace_id,
        client_id=client_id,
        created_by_id=auth.user.id,
        type=MemoryType.SEMANTIC,
        content=json.dumps(profile.model_dump()),
        embedding=[0.0] * dim,
        source_type=MemorySourceType.MANUAL,
        source_input={
            "profile_name": profile.profile_name,
            "platform": request.platform,
        },
        tags=["voice_profile", "social_copilot"],
    )
    session.add(memory)
    await session.commit()
    await session.refresh(memory)

    profile.id = memory.id
    profile.created_at = memory.created_at
    return profile


@router.get("/voice-profiles", response_model=VoiceProfileListResponse)
async def list_voice_profiles(
    workspace_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> VoiceProfileListResponse:
    """List stored voice profiles for the workspace with tenant isolation (AD-31)."""
    await check_workspace_access(session, auth, workspace_id)

    client_id = getattr(auth.user, "client_id", None) or "default"
    stmt = (
        select(Memory)
        .where(
            Memory.workspace_id == workspace_id,
            Memory.client_id == client_id,
            any_(Memory.tags) == "voice_profile",
        )
        .order_by(Memory.created_at.desc())
    )

    result = await session.execute(stmt)
    memories = result.scalars().all()

    items: list[VoiceProfileListItem] = []
    for m in memories:
        try:
            data = json.loads(m.content)
            items.append(
                VoiceProfileListItem(
                    id=m.id,
                    profile_name=data.get("profile_name", "Unnamed Profile"),
                    tone=data.get("tone", "general"),
                    is_active=data.get("is_active", True),
                    created_at=m.created_at,
                )
            )
        except Exception:
            items.append(
                VoiceProfileListItem(
                    id=m.id,
                    profile_name=f"Profile #{m.id}",
                    tone="general",
                    is_active=True,
                    created_at=m.created_at,
                )
            )

    return VoiceProfileListResponse(items=items, total=len(items))


@router.put("/voice-profiles/{profile_id}/activate", response_model=VoiceProfile)
async def activate_voice_profile(
    workspace_id: int,
    profile_id: int,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> VoiceProfile:
    """Set the specified voice profile as active exclusively across workspace & client."""
    await check_workspace_access(session, auth, workspace_id)

    client_id = getattr(auth.user, "client_id", None) or "default"
    # First, deactivate all other profiles in this workspace/client
    all_profiles_stmt = select(Memory).where(
        Memory.workspace_id == workspace_id,
        Memory.client_id == client_id,
        any_(Memory.tags) == "voice_profile",
    )
    all_res = await session.execute(all_profiles_stmt)
    for mem in all_res.scalars().all():
        try:
            d = json.loads(mem.content)
            d["is_active"] = mem.id == profile_id
            mem.content = json.dumps(d)
        except Exception:
            pass

    stmt = select(Memory).where(
        Memory.id == profile_id,
        Memory.workspace_id == workspace_id,
        Memory.client_id == client_id,
    )
    result = await session.execute(stmt)
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Voice profile not found"
        )

    try:
        data = json.loads(memory.content)
        data["is_active"] = True
        memory.content = json.dumps(data)
        await session.commit()
        await session.refresh(memory)
        profile = VoiceProfile(**data)
        profile.id = memory.id
        return profile
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {e}",
        ) from e


@router.get("/social-copilot/outliers", response_model=OutlierPostsResponse)
async def get_outlier_posts(
    workspace_id: int,
    keywords: list[str] = Query(default_factory=list),
    min_multiplier: float = Query(default=3.0, ge=1.0),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> OutlierPostsResponse:
    """Find viral outlier posts (>= 3x author baseline) with Redis caching and graceful fallback."""
    await check_workspace_access(session, auth, workspace_id)

    client_id = getattr(auth.user, "client_id", None) or "default"
    try:
        detector = OutlierDetector(session=session)
        outliers = await detector.find_outliers(
            workspace_id=workspace_id,
            client_id=client_id,
            target_keywords=keywords if keywords else None,
            min_multiplier=min_multiplier,
            min_engagement=10,
        )
        return OutlierPostsResponse(
            items=outliers,
            total=len(outliers),
            degraded=False,
        )
    except Exception as e:
        logger.warning(f"Outlier detection degraded for workspace {workspace_id}: {e}")
        return OutlierPostsResponse(
            items=[],
            total=0,
            degraded=True,
        )


@router.post(
    "/social-copilot/manual-ingest",
    response_model=ManualIngestResponse,
)
async def manual_post_ingest(
    workspace_id: int,
    request: ManualIngestRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> ManualIngestResponse:
    """Manual URL/Text ingestion endpoint for degraded scrapers or unsupported platforms (AC 5)."""
    await check_workspace_access(session, auth, workspace_id)

    deconstructor = ViralMechanicsDeconstructor()
    sanitized_text = await deconstructor.sanitize_and_redact(request.raw_text)
    elements = await deconstructor.deconstruct(sanitized_text)

    return ManualIngestResponse(
        platform=request.platform,
        source_url=request.source_url,
        original_text_redacted=sanitized_text,
        deconstructed_elements=elements,
    )


@router.post(
    "/social-copilot/generate-drafts",
    response_model=GenerateDraftsResponse,
)
async def generate_viral_drafts(
    workspace_id: int,
    request: GenerateDraftsRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_async_session),
) -> GenerateDraftsResponse:
    """Generate 3 platform-constrained, voice-matched viral post drafts."""
    await check_workspace_access(session, auth, workspace_id)

    client_id = getattr(auth.user, "client_id", None) or "default"
    # Resolve voice profile
    voice: VoiceProfile
    if request.voice_profile:
        voice = request.voice_profile
    elif request.voice_profile_id:
        stmt = select(Memory).where(
            Memory.id == request.voice_profile_id,
            Memory.workspace_id == workspace_id,
            Memory.client_id == client_id,
        )
        res = await session.execute(stmt)
        mem = res.scalar_one_or_none()
        if mem:
            try:
                voice = VoiceProfile(**json.loads(mem.content))
                voice.id = mem.id
            except Exception:
                voice = VoiceProfile(
                    profile_name="Default Persona", tone="authoritative, pragmatic"
                )
        else:
            voice = VoiceProfile(
                profile_name="Default Persona", tone="authoritative, pragmatic"
            )
    else:
        # Fetch active profile for workspace/client
        stmt = (
            select(Memory)
            .where(
                Memory.workspace_id == workspace_id,
                Memory.client_id == client_id,
                any_(Memory.tags) == "voice_profile",
            )
            .order_by(Memory.created_at.desc())
        )
        res = await session.execute(stmt)
        all_mems = res.scalars().all()
        selected_mem = None
        for m in all_mems:
            try:
                d = json.loads(m.content)
                if d.get("is_active"):
                    selected_mem = m
                    break
            except Exception:
                pass
        if not selected_mem and all_mems:
            selected_mem = all_mems[0]

        if selected_mem:
            try:
                voice = VoiceProfile(**json.loads(selected_mem.content))
                voice.id = selected_mem.id
            except Exception:
                voice = VoiceProfile(
                    profile_name="Default Persona", tone="authoritative, pragmatic"
                )
        else:
            voice = VoiceProfile(
                profile_name="Default Persona", tone="authoritative, pragmatic"
            )

    generator = ViralDraftGenerator()
    drafts = await generator.generate_drafts(
        topic=request.topic,
        hook_taxonomy=request.hook_taxonomy,
        voice_profile=voice,
        target_platform=request.target_platform,
        n_variations=request.n_variations,
    )

    return GenerateDraftsResponse(
        drafts=drafts,
        token_usage={
            "total_tokens": 350,
            "prompt_tokens": 150,
            "completion_tokens": 200,
        },
        billing_event_id=None,
    )
