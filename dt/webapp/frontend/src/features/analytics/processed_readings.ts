import type { Reading } from "$shared/types";

const averagedReadingFields = [
	"value",
	"raw_value",
	"calibrated_value",
	"normalized_value",
	"dq_score",
] as const;

type AveragedReadingField = (typeof averagedReadingFields)[number];

export type ProcessedReadingsCache = {
	readings: Reading[];
	counts: Map<string, number>;
};

function getReadingTopic(reading: Reading): string | null {
	const topic = (reading as { topic?: unknown }).topic;
	return typeof topic === "string" && topic.length > 0 ? topic : null;
}

function getFiniteReadingValue(value: number | null | undefined): number | null {
	return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function averageReadingField(
	readings: Reading[],
	field: AveragedReadingField,
): number | null | undefined {
	const values = readings
		.map((reading) => getFiniteReadingValue(reading[field]))
		.filter((value): value is number => value !== null);

	if (values.length === 0) {
		return readings[0]?.[field];
	}

	return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function averageReadingFieldWithCount(
	existing: number | null | undefined,
	incoming: number | null | undefined,
	existingCount: number,
): number | null | undefined {
	const existingValue = getFiniteReadingValue(existing);
	const incomingValue = getFiniteReadingValue(incoming);

	if (existingValue === null) {
		return incomingValue ?? existing ?? incoming;
	}

	if (incomingValue === null) {
		return existing;
	}

	return (existingValue * existingCount + incomingValue) / (existingCount + 1);
}

function mergeReadingFlags(
	readings: Reading[],
): Record<string, boolean> | null | undefined {
	const flags: Record<string, boolean> = {};

	for (const reading of readings) {
		for (const [flag, active] of Object.entries(reading.flags ?? {})) {
			if (active) {
				flags[flag] = true;
			}
		}
	}

	return Object.keys(flags).length > 0 ? flags : readings[0]?.flags;
}

function mergeReadingPair(
	existing: Reading,
	incoming: Reading,
	existingCount: number,
): Reading {
	const merged: Reading = {
		...existing,
		unit: existing.unit ?? incoming.unit,
		flags: mergeReadingFlags([existing, incoming]),
	};

	for (const field of averagedReadingFields) {
		merged[field] = averageReadingFieldWithCount(
			existing[field],
			incoming[field],
			existingCount,
		) as Reading[AveragedReadingField];
	}

	return merged;
}

function mergeReadingGroup(readings: Reading[]): Reading {
	if (readings.length === 1) {
		return readings[0];
	}

	const merged = { ...readings[0], flags: mergeReadingFlags(readings) };
	for (const field of averagedReadingFields) {
		merged[field] = averageReadingField(readings, field) as Reading[AveragedReadingField];
	}

	return merged;
}

export function buildProcessedReadingCacheKey(reading: Reading): string | null {
	const topic = getReadingTopic(reading);
	if (!topic || !Number.isFinite(reading.time)) {
		return null;
	}

	return `${topic}:${reading.time}`;
}

export function normalizeProcessedReadings(
	readings: Reading[],
): ProcessedReadingsCache {
	const groups = new Map<string, Reading[]>();
	const orderedKeys: string[] = [];
	const passthrough: Reading[] = [];

	for (const reading of readings) {
		const key = buildProcessedReadingCacheKey(reading);
		if (!key) {
			passthrough.push(reading);
			continue;
		}

		const group = groups.get(key);
		if (group) {
			group.push(reading);
		} else {
			groups.set(key, [reading]);
			orderedKeys.push(key);
		}
	}

	const counts = new Map<string, number>();
	const mergedReadings = orderedKeys.map((key) => {
		const group = groups.get(key) ?? [];
		counts.set(key, group.length);
		return mergeReadingGroup(group);
	});

	return {
		readings: [...mergedReadings, ...passthrough],
		counts,
	};
}

export function mergeProcessedReadingIntoCache(
	readings: Reading[],
	counts: Map<string, number>,
	reading: Reading,
): Reading[] {
	const key = buildProcessedReadingCacheKey(reading);
	if (!key) {
		return [...readings, reading];
	}

	const existingIndex = readings.findIndex(
		(candidate) => buildProcessedReadingCacheKey(candidate) === key,
	);
	if (existingIndex < 0) {
		counts.set(key, 1);
		return [...readings, reading];
	}

	const existingCount = counts.get(key) ?? 1;
	counts.set(key, existingCount + 1);

	return readings.map((candidate, index) =>
		index === existingIndex
			? mergeReadingPair(candidate, reading, existingCount)
			: candidate,
	);
}
