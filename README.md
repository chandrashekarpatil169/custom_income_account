# Custom Product Income Account

Odoo module that allows administrators to select specific products and assign a single income account in Accounting Settings. The selected income account is automatically applied when those products appear on customer invoices.

## Module

| Module | Version | Category |
|--------|---------|----------|
| `custom_income_account` | 18.0.1.0.0 | Accounting |

## Features

- **Configurable Product Selection** — pick which products should use a custom income account via Accounting Settings.
- **Single Income Account Override** — define one income account that auto-applies to selected products on invoices.
- **Invoice Line Automation** — automatically overrides the default income account on invoice lines for the configured products.
- **Settings Integration** — configuration is available directly in **Settings → Accounting**.

## Dependencies

- `account`
- `product`
- `sale_management`
- `accountant`
- `stock`
- `purchase`

## Installation

1. Copy the `custom_income_account` folder into your Odoo addons directory.
2. Update the module list: **Settings → Technical → Update Apps List**.
3. Search for **Custom Product Income Account** and click **Install**.

## Configuration

1. Navigate to **Settings → Accounting**.
2. Under the custom income account section, select the target products.
3. Choose the income account to be used.
4. Save. New invoices containing those products will automatically use the configured income account.

## Requirements

- Odoo 18.0 (Community or Enterprise)
- Python 3.10+

## License

LGPL-3
