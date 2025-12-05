"""
Property-based tests for Slug service.

**Feature: instant-youtube-preview, Property 5: Slug Generation Consistency**
**Validates: Requirements 6.2**

Property: For any video title, generating a slug should produce a valid 
URL-safe string containing only lowercase letters, numbers, and hyphens.
"""

import re
from hypothesis import given, strategies as st, settings

from app.services.slug import SlugService


# Strategy for generating arbitrary video titles
# Include various unicode characters, spaces, special chars, etc.
title_strategy = st.text(
    min_size=0,
    max_size=200,
)

# Strategy for titles with common patterns
common_title_strategy = st.one_of(
    # Normal titles with spaces
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ", min_size=1, max_size=100),
    # Titles with special characters
    st.text(min_size=1, max_size=100),
    # Titles with unicode
    st.text(alphabet="àéîõüñçÀÉÎÕÜÑÇ abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=100),
)


# Valid slug pattern: only lowercase letters, numbers, and hyphens
VALID_SLUG_PATTERN = re.compile(r'^[a-z0-9-]*$')


@settings(max_examples=100)
@given(title=title_strategy)
def test_slug_contains_only_valid_characters(title: str):
    """
    **Feature: instant-youtube-preview, Property 5: Slug Generation Consistency**
    **Validates: Requirements 6.2**
    
    Property: For any video title, the generated slug should contain only
    lowercase letters, numbers, and hyphens.
    """
    service = SlugService()
    
    slug = service.generate_slug(title)
    
    # Property: slug must match valid pattern (lowercase, numbers, hyphens only)
    assert VALID_SLUG_PATTERN.match(slug), f"Slug '{slug}' contains invalid characters"


@settings(max_examples=100)
@given(title=title_strategy)
def test_slug_has_no_consecutive_hyphens(title: str):
    """
    **Feature: instant-youtube-preview, Property 5: Slug Generation Consistency**
    **Validates: Requirements 6.2**
    
    Property: For any video title, the generated slug should not contain
    consecutive hyphens.
    """
    service = SlugService()
    
    slug = service.generate_slug(title)
    
    # Property: no consecutive hyphens
    assert '--' not in slug, f"Slug '{slug}' contains consecutive hyphens"


@settings(max_examples=100)
@given(title=title_strategy)
def test_slug_has_no_leading_or_trailing_hyphens(title: str):
    """
    **Feature: instant-youtube-preview, Property 5: Slug Generation Consistency**
    **Validates: Requirements 6.2**
    
    Property: For any video title, the generated slug should not start or
    end with a hyphen.
    """
    service = SlugService()
    
    slug = service.generate_slug(title)
    
    # Property: no leading or trailing hyphens
    assert not slug.startswith('-'), f"Slug '{slug}' starts with hyphen"
    assert not slug.endswith('-'), f"Slug '{slug}' ends with hyphen"


@settings(max_examples=100)
@given(title=title_strategy)
def test_slug_respects_max_length(title: str):
    """
    **Feature: instant-youtube-preview, Property 5: Slug Generation Consistency**
    **Validates: Requirements 6.2**
    
    Property: For any video title, the generated slug should not exceed
    the maximum length of 100 characters.
    """
    service = SlugService()
    
    slug = service.generate_slug(title)
    
    # Property: slug length must not exceed max
    assert len(slug) <= service.MAX_SLUG_LENGTH, f"Slug '{slug}' exceeds max length"


@settings(max_examples=100)
@given(title=title_strategy)
def test_slug_is_never_empty(title: str):
    """
    **Feature: instant-youtube-preview, Property 5: Slug Generation Consistency**
    **Validates: Requirements 6.2**
    
    Property: For any video title (including empty), the generated slug
    should never be empty (fallback to "untitled").
    """
    service = SlugService()
    
    slug = service.generate_slug(title)
    
    # Property: slug must never be empty
    assert len(slug) > 0, "Slug should never be empty"
    assert slug != "", "Slug should never be empty string"


@settings(max_examples=100)
@given(title=common_title_strategy)
def test_slug_is_lowercase(title: str):
    """
    **Feature: instant-youtube-preview, Property 5: Slug Generation Consistency**
    **Validates: Requirements 6.2**
    
    Property: For any video title, the generated slug should be entirely
    lowercase.
    """
    service = SlugService()
    
    slug = service.generate_slug(title)
    
    # Property: slug must be lowercase
    assert slug == slug.lower(), f"Slug '{slug}' is not lowercase"


@settings(max_examples=100)
@given(title=st.text(min_size=1, max_size=50))
def test_slug_generation_is_deterministic(title: str):
    """
    **Feature: instant-youtube-preview, Property 5: Slug Generation Consistency**
    **Validates: Requirements 6.2**
    
    Property: For any video title, generating a slug multiple times should
    produce the same result.
    """
    service = SlugService()
    
    slug1 = service.generate_slug(title)
    slug2 = service.generate_slug(title)
    
    # Property: slug generation must be deterministic
    assert slug1 == slug2, f"Slug generation not deterministic: '{slug1}' != '{slug2}'"


# ============================================================================
# Property 6: Slug Uniqueness Tests
# ============================================================================

@settings(max_examples=100)
@given(titles=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=20))
def test_ensure_unique_slug_produces_distinct_slugs(titles: list):
    """
    **Feature: instant-youtube-preview, Property 6: Slug Uniqueness**
    **Validates: Requirements 6.3**
    
    Property: For any set of video titles, generating slugs with uniqueness
    enforcement should produce distinct slugs for each video.
    """
    service = SlugService()
    
    generated_slugs = []
    
    for title in titles:
        base_slug = service.generate_slug(title)
        unique_slug = service.ensure_unique_slug(base_slug, generated_slugs)
        generated_slugs.append(unique_slug)
    
    # Property: all generated slugs must be unique
    assert len(generated_slugs) == len(set(generated_slugs)), \
        f"Duplicate slugs found: {generated_slugs}"


@settings(max_examples=100)
@given(base_slug=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=50).filter(lambda s: s and not s.startswith('-') and not s.endswith('-') and '--' not in s),
       existing_count=st.integers(min_value=0, max_value=50))
def test_ensure_unique_slug_with_collisions(base_slug: str, existing_count: int):
    """
    **Feature: instant-youtube-preview, Property 6: Slug Uniqueness**
    **Validates: Requirements 6.3**
    
    Property: For any base slug and any number of existing slugs with the same
    base, ensure_unique_slug should always produce a slug not in the existing set.
    """
    service = SlugService()
    
    # Create existing slugs that would collide
    existing_slugs = [base_slug]
    for i in range(2, existing_count + 2):
        existing_slugs.append(f"{base_slug}-{i}")
    
    unique_slug = service.ensure_unique_slug(base_slug, existing_slugs)
    
    # Property: the returned slug must not be in the existing set
    assert unique_slug not in existing_slugs, \
        f"Slug '{unique_slug}' already exists in {existing_slugs}"


@settings(max_examples=100)
@given(base_slug=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=50).filter(lambda s: s and not s.startswith('-') and not s.endswith('-') and '--' not in s))
def test_ensure_unique_slug_returns_base_when_no_collision(base_slug: str):
    """
    **Feature: instant-youtube-preview, Property 6: Slug Uniqueness**
    **Validates: Requirements 6.3**
    
    Property: For any base slug with no existing collisions, ensure_unique_slug
    should return the base slug unchanged.
    """
    service = SlugService()
    
    # Empty existing slugs - no collision possible
    existing_slugs = []
    
    unique_slug = service.ensure_unique_slug(base_slug, existing_slugs)
    
    # Property: when no collision, return base slug as-is
    assert unique_slug == base_slug, \
        f"Expected '{base_slug}' but got '{unique_slug}'"


@settings(max_examples=100)
@given(titles=st.lists(st.just("same-title"), min_size=2, max_size=20))
def test_ensure_unique_slug_handles_identical_titles(titles: list):
    """
    **Feature: instant-youtube-preview, Property 6: Slug Uniqueness**
    **Validates: Requirements 6.3**
    
    Property: For any number of identical titles, generating slugs with
    uniqueness enforcement should produce distinct slugs with numeric suffixes.
    """
    service = SlugService()
    
    generated_slugs = []
    
    for title in titles:
        base_slug = service.generate_slug(title)
        unique_slug = service.ensure_unique_slug(base_slug, generated_slugs)
        generated_slugs.append(unique_slug)
    
    # Property: all generated slugs must be unique
    assert len(generated_slugs) == len(set(generated_slugs)), \
        f"Duplicate slugs found: {generated_slugs}"
    
    # Property: first slug should be the base, rest should have suffixes
    assert generated_slugs[0] == "same-title", \
        f"First slug should be 'same-title', got '{generated_slugs[0]}'"
    
    for i, slug in enumerate(generated_slugs[1:], start=2):
        assert slug == f"same-title-{i}", \
            f"Expected 'same-title-{i}', got '{slug}'"
