# tests/test_ticket_operations.py

- TestTicketOperations · class · L22-L197 — class TestTicketOperations
- config · method · L26-L31 — def config(self)
- client · method · L34-L35 — def client(self, config)
- test_get_tickets_defaults_to_open · method · L38-L47 — async def
  test_get_tickets_defaults_to_open(self, client)
- test_get_tickets_with_status_filter · method · L50-L56 — async def
  test_get_tickets_with_status_filter(self, client)
- test_get_ticket_by_ref · method · L59-L70 — async def test_get_ticket_by_ref(self, client)
- test_search_tickets · method · L73-L87 — async def test_search_tickets(self, client)
- test_create_ticket · method · L90-L104 — async def test_create_ticket(self, client)
- test_create_ticket_fk_soc_alias · method · L107-L114 — async def test_create_ticket_fk_soc_alias(self,
  client)
- test_create_ticket_requires_subject_and_message · method · L117-L123 — async def
  test_create_ticket_requires_subject_and_message(self, client)
- test_add_ticket_message_with_track_id · method · L126-L138 — async def
  test_add_ticket_message_with_track_id(self, client)
- test_add_ticket_message_resolves_ref · method · L141-L153 — async def
  test_add_ticket_message_resolves_ref(self, client)
- test_add_ticket_message_requires_ref_or_track_id · method · L156-L162 — async def
  test_add_ticket_message_requires_ref_or_track_id(self, client)
- test_update_ticket_by_id · method · L165-L173 — async def test_update_ticket_by_id(self, client)
- test_update_ticket_resolves_ref · method · L176-L188 — async def test_update_ticket_resolves_ref(self,
  client)
- test_update_ticket_requires_id_or_ref · method · L191-L197 — async def
  test_update_ticket_requires_id_or_ref(self, client)
- TestTicketAdaptations · class · L200-L224 — class TestTicketAdaptations
- client · method · L204-L205 — def client(self)
- test_get_tickets_page_is_zero_based · method · L209-L212 — async def
  test_get_tickets_page_is_zero_based(self, client, page, expected)
- test_get_tickets_empty_list_on_404 · method · L215-L218 — async def
  test_get_tickets_empty_list_on_404(self, client)
- test_get_ticket_by_ref_is_url_encoded · method · L221-L224 — async def
  test_get_ticket_by_ref_is_url_encoded(self, client)
