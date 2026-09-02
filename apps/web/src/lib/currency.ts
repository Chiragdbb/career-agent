export type CurrencyOption = {
  code: string;
  name: string;
};

/** Major currencies for salary preferences (ISO 4217). */
export const MAIN_CURRENCIES: CurrencyOption[] = [
  { code: "USD", name: "US Dollar" },
  { code: "EUR", name: "Euro" },
  { code: "GBP", name: "British Pound" },
  { code: "JPY", name: "Japanese Yen" },
  { code: "CHF", name: "Swiss Franc" },
  { code: "CAD", name: "Canadian Dollar" },
  { code: "AUD", name: "Australian Dollar" },
  { code: "NZD", name: "New Zealand Dollar" },
  { code: "CNY", name: "Chinese Yuan" },
  { code: "HKD", name: "Hong Kong Dollar" },
  { code: "SGD", name: "Singapore Dollar" },
  { code: "INR", name: "Indian Rupee" },
  { code: "KRW", name: "South Korean Won" },
  { code: "MXN", name: "Mexican Peso" },
  { code: "BRL", name: "Brazilian Real" },
  { code: "ZAR", name: "South African Rand" },
  { code: "SEK", name: "Swedish Krona" },
  { code: "NOK", name: "Norwegian Krone" },
  { code: "DKK", name: "Danish Krone" },
  { code: "PLN", name: "Polish Złoty" },
  { code: "TRY", name: "Turkish Lira" },
  { code: "AED", name: "UAE Dirham" },
  { code: "SAR", name: "Saudi Riyal" },
  { code: "THB", name: "Thai Baht" },
  { code: "MYR", name: "Malaysian Ringgit" },
  { code: "PHP", name: "Philippine Peso" },
  { code: "IDR", name: "Indonesian Rupiah" },
  { code: "TWD", name: "Taiwan Dollar" },
  { code: "PKR", name: "Pakistani Rupee" },
  { code: "ILS", name: "Israeli Shekel" },
  { code: "CZK", name: "Czech Koruna" },
  { code: "HUF", name: "Hungarian Forint" },
  { code: "RON", name: "Romanian Leu" },
  { code: "BGN", name: "Bulgarian Lev" },
  { code: "COP", name: "Colombian Peso" },
  { code: "CLP", name: "Chilean Peso" },
  { code: "ARS", name: "Argentine Peso" },
  { code: "EGP", name: "Egyptian Pound" },
  { code: "NGN", name: "Nigerian Naira" },
  { code: "VND", name: "Vietnamese Dong" },
  { code: "UAH", name: "Ukrainian Hryvnia" },
];

const LOCALE_REGION_CURRENCY: Record<string, string> = {
  us: "USD",
  gb: "GBP",
  uk: "GBP",
  in: "INR",
  au: "AUD",
  ca: "CAD",
  sg: "SGD",
  jp: "JPY",
  cn: "CNY",
  hk: "HKD",
  kr: "KRW",
  mx: "MXN",
  br: "BRL",
  za: "ZAR",
  se: "SEK",
  no: "NOK",
  dk: "DKK",
  pl: "PLN",
  tr: "TRY",
  ae: "AED",
  sa: "SAR",
  th: "THB",
  my: "MYR",
  ph: "PHP",
  id: "IDR",
  tw: "TWD",
  pk: "PKR",
  il: "ILS",
  cz: "CZK",
  hu: "HUF",
  ro: "RON",
  bg: "BGN",
  co: "COP",
  cl: "CLP",
  ar: "ARS",
  eg: "EGP",
  ng: "NGN",
  vn: "VND",
  ua: "UAH",
  nz: "NZD",
  ch: "CHF",
  de: "EUR",
  fr: "EUR",
  es: "EUR",
  it: "EUR",
  nl: "EUR",
  ie: "EUR",
  at: "EUR",
  be: "EUR",
  pt: "EUR",
  fi: "EUR",
};

const MAIN_CURRENCY_CODES = new Set(MAIN_CURRENCIES.map((c) => c.code));

export function detectLocaleCurrency(): string {
  if (typeof navigator === "undefined") {
    return "USD";
  }
  const locale = navigator.language || "en-US";
  const parts = locale.toLowerCase().replace("_", "-").split("-");
  const region = parts.length > 1 ? parts[parts.length - 1] : parts[0];
  const currency = LOCALE_REGION_CURRENCY[region] ?? "USD";
  return MAIN_CURRENCY_CODES.has(currency) ? currency : "USD";
}

export function currencyOptions(selected?: string): CurrencyOption[] {
  const selectedCode = (selected ?? detectLocaleCurrency()).toUpperCase();
  const byCode = new Map(MAIN_CURRENCIES.map((c) => [c.code, c]));

  if (!byCode.has(selectedCode)) {
    byCode.set(selectedCode, { code: selectedCode, name: selectedCode });
  }

  return [...byCode.values()].sort((a, b) => a.code.localeCompare(b.code));
}

export function formatCurrencyLabel(option: CurrencyOption): string {
  return `${option.code} — ${option.name}`;
}

export function localeHint(): string {
  if (typeof navigator === "undefined") {
    return "en-US";
  }
  return navigator.language || "en-US";
}

/** Codes accepted when merging LLM-parsed salary currency (matches MAIN_CURRENCIES). */
export const MAIN_CURRENCY_CODE_LIST = [...MAIN_CURRENCY_CODES];
