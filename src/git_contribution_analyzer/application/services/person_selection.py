from __future__ import annotations

from typing import Any, Protocol

from git_contribution_analyzer.domain.errors import IdentityResolutionError
from git_contribution_analyzer.domain.models.person_selection import (
    PersonExclusion,
    PersonSelection,
    SelectionMode,
)


class PersonSelectionStore(Protocol):
    def resolve_people(
        self, selectors: tuple[str, ...], *, require_confirmed: bool
    ) -> list[dict[str, Any]]: ...

    def list_people_for_analysis(self) -> list[dict[str, Any]]: ...


def select_people(
    store: PersonSelectionStore,
    *,
    person_selectors: tuple[str, ...],
    all_people: bool,
    exclude_selectors: tuple[str, ...],
) -> tuple[tuple[dict[str, Any], ...], PersonSelection]:
    if all_people:
        return _select_all(store, exclude_selectors)
    people = store.resolve_people(person_selectors, require_confirmed=True)
    _reject_duplicate_people(people)
    for person in people:
        if str(person["kind"]) != "HUMAN":
            raise IdentityResolutionError(
                f"Person is not eligible for assessment: {person['name']} ({person['kind']})"
            )
    ordered = tuple(sorted(people, key=lambda value: str(value["id"])))
    return ordered, PersonSelection(
        mode=SelectionMode.EXPLICIT,
        requested_selectors=person_selectors,
        included_person_ids=tuple(str(person["id"]) for person in ordered),
        exclusions=(),
    )


def _select_all(
    store: PersonSelectionStore,
    exclude_selectors: tuple[str, ...],
) -> tuple[tuple[dict[str, Any], ...], PersonSelection]:
    all_people = store.list_people_for_analysis()
    exclusions: list[PersonExclusion] = []
    eligible: dict[str, dict[str, Any]] = {}
    for person in sorted(all_people, key=lambda value: str(value["id"])):
        person_id = str(person["id"])
        if not bool(person["confirmed"]):
            exclusions.append(PersonExclusion(None, person_id, "UNCONFIRMED"))
        elif str(person["kind"]) != "HUMAN":
            exclusions.append(PersonExclusion(None, person_id, "KIND_NOT_ALLOWED"))
        else:
            eligible[person_id] = person

    explicitly_excluded = store.resolve_people(
        exclude_selectors, require_confirmed=False
    )
    _reject_duplicate_people(explicitly_excluded)
    for selector, person in zip(exclude_selectors, explicitly_excluded, strict=True):
        person_id = str(person["id"])
        if person_id in eligible:
            eligible.pop(person_id)
            exclusions.append(
                PersonExclusion(selector, person_id, "EXPLICITLY_EXCLUDED")
            )

    if not eligible:
        raise IdentityResolutionError("Selection contains no people eligible for assessment")
    ordered = tuple(eligible[person_id] for person_id in sorted(eligible))
    return ordered, PersonSelection(
        mode=SelectionMode.ALL,
        requested_selectors=(),
        included_person_ids=tuple(str(person["id"]) for person in ordered),
        exclusions=tuple(exclusions),
    )


def _reject_duplicate_people(people: list[dict[str, Any]]) -> None:
    person_ids = [str(person["id"]) for person in people]
    if len(person_ids) != len(set(person_ids)):
        raise IdentityResolutionError("Multiple selectors resolve to the same person")
