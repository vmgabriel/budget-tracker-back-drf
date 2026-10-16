# Testing Strategy
- **Unit**: No DB. Mock repositories/clocks. Use `FakeRepository`/`FakeClock`. Mark with `@pytest.mark.unit`.
- **Integration**: Real DB (PostgreSQL in Docker). Use `factory-boy`. Mark with `@pytest.mark.integration` and `@pytest.mark.django_db(transaction=True)`.
- **Architecture Test**: `test_architecture.py` enforces no framework imports in domain/app.
- **Rule**: Never test real LLM connectivity in CI. Mock the port.
