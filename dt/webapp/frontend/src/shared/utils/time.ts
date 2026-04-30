export const APP_DATE_LOCALE = "en-GB";
export const APP_TIME_ZONE = "Europe/Brussels";

const chartFormatter = new Intl.DateTimeFormat(APP_DATE_LOCALE, {
  timeZone: APP_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

const displayFormatter = new Intl.DateTimeFormat(APP_DATE_LOCALE, {
  timeZone: APP_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

type DateParts = {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
  second: string;
};

export function formatChartTime(value: number): string {
  if (!Number.isFinite(value)) {
    return "";
  }

  const date = new Date(value);
  const parts = getDateParts(date);
  const milliseconds = String(date.getUTCMilliseconds()).padStart(3, "0");
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}.${milliseconds}`;
}

export function formatDisplayTime(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }

  return displayFormatter.format(new Date(value));
}

function getDateParts(date: Date): DateParts {
  const values = Object.fromEntries(
    chartFormatter
      .formatToParts(date)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );

  return {
    year: String(values.year),
    month: String(values.month),
    day: String(values.day),
    hour: String(values.hour),
    minute: String(values.minute),
    second: String(values.second),
  };
}
