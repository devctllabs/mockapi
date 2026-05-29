// @ts-nocheck -- mockapi template source; stripped during generation
export const visible = <T extends Record<string, unknown>>(
  records: T[],
  deletedAtField = 'deletedAt',
) => records.filter((record) => !record[deletedAtField])
