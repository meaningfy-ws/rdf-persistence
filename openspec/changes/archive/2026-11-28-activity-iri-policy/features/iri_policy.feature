# Signed off by the developer on 2026-11-25 (evidence/clarity-gate.md). Task 1.7 appends these
# three scenarios verbatim to tests/feature/iri_policy.feature, under its existing Background,
# in the same commit as their steps in tests/feature/test_iri_policy.py.

  # spec: rp-iri-policy / Without a policy, IRIs are today's (issue #197, acceptance 1)
  Scenario: Without an activity template, an activity is a urn:uuid
    Given Ada has a library with a book
    When Ada moves the book to its next state with a comment
    Then the move's activity IRI is "urn:uuid:" followed by a UUID
    And the book's transitions name that activity

  # spec: rp-iri-policy / transitions and comments still find their activity (issue #197, acceptance 2)
  Scenario: Under an activity template, every activity lives under its tenant
    Given the library service runs under the example policy with activity template "{tenant}/activity/{id}"
    And Ada has a library with a book
    When Ada moves the book to its next state with a comment
    And Ada posts a comment on the book
    And Ada replaces the book with a new label
    Then each of the three activity IRIs is the library IRI, "/activity/" and a UUID
    And the book's transitions name the move's activity
    And the comment's thread names the comment's activity
    And the library's provenance holds the three activities and no "urn:uuid:" IRI

  # spec: rp-iri-policy / a changed activity template (issue #197, acceptance 3)
  Scenario: A restart under another activity template is refused
    Given the library service has started once with no activity template
    When it is restarted with activity template "{tenant}/activity/{id}"
    Then start-up fails naming "activity_template"
    And no IRI has been minted
