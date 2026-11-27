# tests/test_invoice_atomic.py

- TestInvoiceAtomic · class · L8-L164 — class TestInvoiceAtomic
- client · method · L11-L16 — def client(self)
- test_add_invoice_line · method · L19-L43 — async def test_add_invoice_line(self, mock_request, client)
- test_update_invoice_line · method · L46-L76 — async def test_update_invoice_line(self, mock_request,
  client)
- test_update_invoice_line_unknown_line · method · L79-L88 — async def
  test_update_invoice_line_unknown_line(self, mock_request, client)
- test_add_invoice_line_5xx_after_insert · method · L91-L101 — async def
  test_add_invoice_line_5xx_after_insert(self, mock_request, client)
- test_add_invoice_line_5xx_without_insert · method · L104-L115 — async def
  test_add_invoice_line_5xx_without_insert(self, mock_request, client)
- test_delete_invoice_line · method · L118-L129 — async def test_delete_invoice_line(self, mock_request,
  client)
- test_validate_invoice · method · L132-L144 — async def test_validate_invoice(self, mock_request,
  client)
- test_line_vat_is_sent_as_tva_tx · method · L147-L164 — async def test_line_vat_is_sent_as_tva_tx(self,
  mock_request, client)
