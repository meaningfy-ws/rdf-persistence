Feature: A consumer's write rules refuse in its own terms and find what a write clashes with
  # Derives from: EPIC consumer-write-rules (DEC-4, DEC-5, DEC-7); issues #397, #386.
  # The toy service registers HeldKeyProblem and a rule for Book that refuses an isbn
  # another readable book holds, naming that book.

  Background:
    Given the toy service with the held-isbn rule and HeldKeyProblem registered
    And a tenant where the writer may write books

  Scenario: a rule refuses with the consumer's problem and names the holder
    Given a stored book with isbn "978-0"
    When the writer creates another book with isbn "978-0"
    Then the answer is 409 with the problem type of HeldKeyProblem
    And the problem's holder is the stored book
    And no second book is stored

  Scenario: a holder in another tenant is not found
    Given a book with isbn "978-0" stored only in another tenant
    When the writer creates a book with isbn "978-0"
    Then the rule finds no holder and the book is created

  Scenario: a holder the writer may not read is not named
    Given a stored book with isbn "978-0" that the writer may not read
    When the writer creates a book with isbn "978-0"
    Then the rule finds no holder
    And the answer is the key-conflict problem, which names no holder

  Scenario: a rule under unit test with the testkit's reader
    Given a fake reader seeded with two books with isbn "978-0", one unreadable by the writer
    When the held-isbn rule is called for a new book with isbn "978-0"
    Then it refuses naming only the readable book
    And the fake reader recorded one find call for Book with isbn "978-0"
