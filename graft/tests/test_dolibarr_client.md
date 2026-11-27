# tests/test_dolibarr_client.py

- TestDolibarrClient · class · L10-L264 — class TestDolibarrClient
- test_config_validation · method · L13-L32 — def test_config_validation(self)
- test_client_session_management · method · L35-L53 — async def test_client_session_management(self)
- test_context_manager · method · L56-L67 — async def test_context_manager(self)
- test_successful_api_request · method · L71-L89 — async def test_successful_api_request(self,
  mock_request)
- test_api_error_handling · method · L93-L112 — async def test_api_error_handling(self, mock_request)
- test_validation_error_on_missing_ref · method · L115-L130 — async def
  test_validation_error_on_missing_ref(self)
- test_autogen_ref_when_enabled · method · L133-L150 — async def test_autogen_ref_when_enabled(self)
- test_product_validation_requires_price_field · method · L153-L167 — async def
  test_product_validation_requires_price_field(self)
- test_product_validation_allows_price_ttc · method · L170-L184 — async def
  test_product_validation_allows_price_ttc(self)
- test_project_validation_missing_socid · method · L187-L201 — async def
  test_project_validation_missing_socid(self)
- test_project_autogen_ref_when_enabled · method · L204-L220 — async def
  test_project_autogen_ref_when_enabled(self)
- test_internal_error_correlation_id · method · L224-L242 — async def
  test_internal_error_correlation_id(self, mock_request)
- test_url_building · method · L244-L264 — def test_url_building(self)
- TestDolibarrAPIError · class · L267-L288 — class TestDolibarrAPIError
- test_error_creation · method · L270-L280 — def test_error_creation(self)
- test_error_without_optional_params · method · L282-L288 — def test_error_without_optional_params(self)
- TestDolibarrIntegration · class · L293-L311 — class TestDolibarrIntegration
- test_real_connection · method · L297-L311 — async def test_real_connection(self)
