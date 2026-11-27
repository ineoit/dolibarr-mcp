# src/dolibarr_mcp/dolibarr_client.py

- DolibarrAPIError · class · L17-L24 — class DolibarrAPIError(Exception)
- __init__ · method · L20-L24 — def __init__(self, message: str, status_code: Optional[int] = None,
  response_data: Optional[Dict] = None)
- DolibarrValidationError · class · L27-L28 — class DolibarrValidationError(DolibarrAPIError)
- DolibarrClient · class · L31-L1169 — class DolibarrClient
- __init__ · method · L34-L49 — def __init__(self, config: Config)
- __aenter__ · method · L51-L54 — async def __aenter__(self)
- __aexit__ · method · L56-L58 — async def __aexit__(self, exc_type, exc_val, exc_tb)
- start_session · method · L60-L70 — async def start_session(self)
- close_session · method · L72-L76 — async def close_session(self)
- \_extract_identifier · method · L79-L87 — def \_extract_identifier(response: Any) -> Any
- \_merge_payload · method · L90-L97 — def \_merge_payload(data: Optional\[Dict[str, Any]\] = None,
  \*\*kwargs) -> Dict[str, Any]
- request · method · L100-L108 — async def request( self, method: str, endpoint: str, params:
  Optional[Dict] = None, data: Optional[Dict] = None ) -> Dict[str, Any]
- \_build_url · method · L110-L114 — def \_build_url(self, endpoint: str) -> str
- \_mask_api_key · method · L116-L122 — def \_mask_api_key(self) -> str
- \_now_iso · method · L125-L127 — def \_now_iso() -> str
- \_generate_correlation_id · method · L130-L132 — def \_generate_correlation_id() -> str
- \_generate_reference · method · L134-L138 — def \_generate_reference(self) -> str
- \_build_validation_error · method · L140-L157 — def \_build_validation_error( self, endpoint: str,
  missing_fields: Optional\[List[str]\] = None, invalid_fields: Optional\[List\[Dict[str, str]\]\] =
  None, message: str = "Validation failed", status: int = 400, ) -> Dict[str, Any]
- \_upstream_message · method · L160-L171 — def \_upstream_message(response_data: Any) -> Optional[str]
- \_build_internal_error · method · L173-L182 — def \_build_internal_error(self, endpoint: str, message:
  str, correlation_id: str) -> Dict[str, Any]
- \_apply_aliases · method · L184-L191 — def \_apply_aliases(self, payload: Dict[str, Any], aliases:
  Dict\[str, List[str]\]) -> None
- \_validate_payload · method · L193-L263 — def \_validate_payload( self, endpoint: str, payload:
  Dict[str, Any], required_fields: List[str], aliases: Optional\[Dict\[str, List[str]\]\] = None,
  numeric_positive: Optional\[List[str]\] = None, enum_fields: Optional\[Dict\[str, List[Any]\]\] = None,
  required_any_of: Optional\[List\[List[str]\]\] = None, non_empty_fields: Optional\[List[str]\] = None,
  ) -> Dict[str, Any]
- \_make_request · method · L265-L428 — async def \_make_request( self, method: str, endpoint: str,
  params: Optional[Dict] = None, data: Optional[Dict] = None ) -> Dict[str, Any]
- test_connection · method · L434-L436 — async def test_connection(self) -> Dict[str, Any]
- get_status · method · L438-L467 — async def get_status(self) -> Dict[str, Any]
- \_get_list · method · L473-L481 — async def \_get_list(self, endpoint: str, params: Dict[str, Any]) ->
  List\[Dict[str, Any]\]
- \_apply_page · method · L484-L491 — def \_apply_page(params: Dict[str, Any], page: Optional[int]) ->
  None
- get_users · method · L493-L499 — async def get_users(self, limit: int = 100, page: int = 1) ->
  List\[Dict[str, Any]\]
- get_user_by_id · method · L501-L503 — async def get_user_by_id(self, user_id: int) -> Dict[str, Any]
- create_user · method · L505-L513 — async def create_user( self, data: Optional\[Dict[str, Any]\] =
  None, \*\*kwargs, ) -> Dict[str, Any]
- update_user · method · L515-L523 — async def update_user( self, user_id: int, data:
  Optional\[Dict\[str, Any\]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- delete_user · method · L525-L527 — async def delete_user(self, user_id: int) -> Dict[str, Any]
- search_customers · method · L533-L537 — async def search_customers(self, sqlfilters: str, limit: int =
  20\) -> List\[Dict[str, Any]\]
- get_customers · method · L539-L545 — async def get_customers(self, limit: int = 100, page: int = 1) ->
  List\[Dict[str, Any]\]
- get_customer_by_id · method · L547-L549 — async def get_customer_by_id(self, customer_id: int) ->
  Dict[str, Any]
- create_customer · method · L551-L578 — async def create_customer( self, data: Optional\[Dict\[str,
  Any\]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- update_customer · method · L580-L594 — async def update_customer( self, customer_id: int, data:
  Optional\[Dict[str, Any]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- delete_customer · method · L596-L598 — async def delete_customer(self, customer_id: int) -> Dict\[str,
  Any\]
- search_products · method · L604-L608 — async def search_products(self, sqlfilters: str, limit: int =
  20\) -> List\[Dict[str, Any]\]
- get_products · method · L610-L614 — async def get_products(self, limit: int = 100) -> List\[Dict\[str,
  Any\]\]
- get_product_by_id · method · L616-L618 — async def get_product_by_id(self, product_id: int) ->
  Dict[str, Any]
- create_product · method · L620-L638 — async def create_product( self, data: Optional\[Dict[str, Any]\]
  = None, \*\*kwargs, ) -> Dict[str, Any]
- update_product · method · L640-L648 — async def update_product( self, product_id: int, data:
  Optional\[Dict[str, Any]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- delete_product · method · L650-L652 — async def delete_product(self, product_id: int) -> Dict[str, Any]
- get_invoices · method · L658-L691 — async def get_invoices( self, limit: int = 100, status:
  Optional[str] = None, customer_id: Optional[int] = None, page: int = 0, sortfield: Optional[str] =
  None, sortorder: Optional[str] = None, ) -> List\[Dict[str, Any]\]
- get_invoice_by_id · method · L693-L715 — async def get_invoice_by_id(self, invoice_id: int) ->
  Dict[str, Any]
- \_map_line_vat · method · L718-L726 — def \_map_line_vat(line: Dict[str, Any]) -> None
- create_invoice · method · L728-L757 — async def create_invoice( self, data: Optional\[Dict[str, Any]\]
  = None, \*\*kwargs, ) -> Dict[str, Any]
- update_invoice · method · L759-L767 — async def update_invoice( self, invoice_id: int, data:
  Optional\[Dict[str, Any]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- delete_invoice · method · L769-L771 — async def delete_invoice(self, invoice_id: int) -> Dict[str, Any]
- add_invoice_line · method · L773-L806 — async def add_invoice_line( self, invoice_id: int, data:
  Optional\[Dict[str, Any]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- \_invoice_line_ids · method · L808-L816 — async def \_invoice_line_ids(self, invoice_id: int) ->
  Optional[set]
- update_invoice_line · method · L818-L856 — async def update_invoice_line( self, invoice_id: int,
  line_id: int, data: Optional\[Dict[str, Any]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- delete_invoice_line · method · L867-L869 — async def delete_invoice_line(self, invoice_id: int,
  line_id: int) -> Dict[str, Any]
- validate_invoice · method · L871-L877 — async def validate_invoice(self, invoice_id: int, warehouse_id:
  int = 0, not_trigger: int = 0) -> Dict[str, Any]
- get_orders · method · L883-L890 — async def get_orders(self, limit: int = 100, status: Optional[str] =
  None) -> List\[Dict[str, Any]\]
- get_order_by_id · method · L892-L894 — async def get_order_by_id(self, order_id: int) -> Dict[str, Any]
- create_order · method · L896-L904 — async def create_order( self, data: Optional\[Dict[str, Any]\] =
  None, \*\*kwargs, ) -> Dict[str, Any]
- update_order · method · L906-L914 — async def update_order( self, order_id: int, data:
  Optional\[Dict[str, Any]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- delete_order · method · L916-L918 — async def delete_order(self, order_id: int) -> Dict[str, Any]
- get_contacts · method · L924-L928 — async def get_contacts(self, limit: int = 100) -> List\[Dict\[str,
  Any\]\]
- get_contact_by_id · method · L930-L932 — async def get_contact_by_id(self, contact_id: int) ->
  Dict[str, Any]
- create_contact · method · L934-L942 — async def create_contact( self, data: Optional\[Dict[str, Any]\]
  = None, \*\*kwargs, ) -> Dict[str, Any]
- update_contact · method · L944-L952 — async def update_contact( self, contact_id: int, data:
  Optional\[Dict[str, Any]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- delete_contact · method · L954-L956 — async def delete_contact(self, contact_id: int) -> Dict[str, Any]
- get_projects · method · L962-L969 — async def get_projects(self, limit: int = 100, page: int = 1,
  status: Optional[int] = None) -> List\[Dict[str, Any]\]
- get_project_by_id · method · L971-L973 — async def get_project_by_id(self, project_id: int) ->
  Dict[str, Any]
- search_projects · method · L975-L979 — async def search_projects(self, sqlfilters: str, limit: int =
  20\) -> List\[Dict[str, Any]\]
- create_project · method · L981-L992 — async def create_project(self, data: Optional\[Dict[str, Any]\] =
  None, \*\*kwargs) -> Dict[str, Any]
- update_project · method · L994-L997 — async def update_project(self, project_id: int, data:
  Optional\[Dict[str, Any]\] = None, \*\*kwargs) -> Dict[str, Any]
- delete_project · method · L999-L1001 — async def delete_project(self, project_id: int) -> Dict\[str,
  Any\]
- get_documents · method · L1007-L1020 — async def get_documents( self, modulepart: str, ref:
  Optional[str] = None, id: Optional[int] = None, ) -> List\[Dict[str, Any]\]
- download_document · method · L1022-L1025 — async def download_document(self, modulepart: str,
  original_file: str) -> Dict[str, Any]
- get_tickets · method · L1031-L1045 — async def get_tickets(self, limit: int = 100, page: int = 1,
  status: Optional[int] = None) -> List\[Dict[str, Any]\]
- get_ticket_by_ref · method · L1047-L1053 — async def get_ticket_by_ref(self, ref: str) -> Dict\[str,
  Any\]
- search_tickets · method · L1055-L1058 — async def search_tickets(self, sqlfilters: str, limit: int =
  20\) -> List\[Dict[str, Any]\]
- create_ticket · method · L1060-L1075 — async def create_ticket(self, data: Optional\[Dict[str, Any]\] =
  None, \*\*kwargs) -> Dict[str, Any]
- \_resolve_ticket_track_id · method · L1077-L1092 — async def \_resolve_ticket_track_id(self, ref: str)
  -> str
- add_ticket_message · method · L1094-L1115 — async def add_ticket_message(self, data:
  Optional\[Dict[str, Any]\] = None, \*\*kwargs) -> Dict[str, Any]
- update_ticket · method · L1117-L1155 — async def update_ticket( self, ticket_id: Optional[int] = None,
  ref: Optional[str] = None, data: Optional\[Dict[str, Any]\] = None, \*\*kwargs, ) -> Dict[str, Any]
- dolibarr_raw_api · method · L1161-L1169 — async def dolibarr_raw_api( self, method: str, endpoint: str,
  params: Optional[Dict] = None, data: Optional[Dict] = None ) -> Dict[str, Any]
