Feature: Every change to a library leaves one record, and messages carry it onwards
  As a librarian, and as a team that builds on the library service
  I want each change recorded once as an activity and handed to whoever reacts to it
  So that the history is kept and follow-up work runs apart from the change itself

  # Recording: every commit leaves one activity

  # spec: rp-messages / a generic replace
  Scenario: A replaced book is recorded as one replacement
    Given Ada's library holds a book
    When Ada replaces the book through the service
    Then one replacement is recorded
    And the replacement is by Ada
    And the replacement generated the book
    And the replacement invalidated the book
    And the generated version is not the invalidated one

  # spec: rp-messages / a refused commit
  Scenario: A refused change leaves no record
    Given the library holds a book
    And the librarian holds an old version of the book
    When the librarian replaces the book with that old version
    Then the change is refused as a conflict
    And the records are as they were

  # spec: rp-messages / a commit of mixed changes
  Scenario: A change that adds one book and removes another is one plain activity
    Given the library holds a book
    When one change adds a second book and removes the first, serving no command
    Then one plain activity is recorded for it
    And the activity generated the second book
    And the activity invalidated the first book

  # Keeping: a record outlives the book it names

  # spec: rp-messages / a removed book
  Scenario: A removed book keeps its record
    Given the library holds a book
    When the book is removed
    Then the records hold the addition of the book
    And the records hold a removal naming the book

  # spec: rp-messages / a reused activity IRI
  Scenario: A command cannot be recorded twice
    Given a shelving command was recorded
    When a second change serves a command with the same identity
    Then the change is refused as a conflict naming that identity
    And the records are as they were

  # Observing: one message per commit, along the class hierarchy

  # spec: rp-messages / a specialised transition
  Scenario: An observer of transitions hears an approval
    Given an observer of transitions
    And the library holds a book
    When the librarian approves the book
    Then the observer receives one message
    And the message is the approval
    And the message carries the generation of the book

  # spec: rp-messages / a failing observer
  Scenario: A failing observer does not stop the next one
    Given two observers of every activity, the first of which fails
    And the library holds a book
    When the librarian approves the book
    Then the failure is logged
    And the second observer still receives the approval

  # spec: rp-messages / a false conflict
  Scenario: A commit that looked like a conflict is recorded but not announced
    Given an observer of every activity
    And the library holds a book
    When another writer replaces the book before the librarian's change is confirmed
    Then the librarian sees a conflict
    And the librarian's replacement is recorded
    And the observer receives no replacement

  # Handling: a command goes to the nearest handler

  # spec: rp-messages / an extension without its own handler
  Scenario: An approval without its own handler is run as a transition
    Given the library holds a book
    When the librarian approves the book
    Then the book is in review
    And the stored activity is an approval

  # spec: rp-messages / a standard command without a handler
  Scenario: A command with no handler is refused by name
    When a command to delete a file is handled
    Then the command is refused with an error naming the file deletion

  # Provenance: the toolkit fills it

  # spec: rp-messages / a forged principal
  Scenario: A command that names another principal is refused
    Given the library holds a book
    When the librarian approves the book naming Bob as the agent
    Then the command is refused as invalid
    And nothing is written

  # spec: rp-messages / a statement about another resource
  Scenario: A command's record cannot state facts about another resource
    Given the library holds a book
    And a shelving record that also states a title for that book
    When a change serves that record
    Then the change is refused
    And nothing is written

  # spec: rp-messages / a spent record
  Scenario: A used-up record cannot serve a second change
    Given a shelving record whose change was refused as a conflict
    When a second change serves the same record
    Then the second change is refused

  # spec: rp-messages / a batched unit of work
  Scenario: A change in batches records one activity per batch
    Given a change that adds four books in batches of two
    When the change commits
    Then two activities are recorded, one per batch

  # Bounds: messages raised while handling stay bounded

  # spec: rp-messages / a loop
  Scenario: A command that keeps sending itself is stopped
    Given a bus that handles at most 3 commands in one call
    And an observer that answers every shelving with another shelving
    And the library holds two books
    When a shelving command is handled
    Then the call stops with an error naming the limit of 3
