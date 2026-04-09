ALTER TABLE estimates ADD COLUMN IF NOT EXISTS actual_total_cost NUMERIC(12,2);
ALTER TABLE estimates ADD COLUMN IF NOT EXISTS actual_cost_date DATE;
ALTER TABLE estimates ADD COLUMN IF NOT EXISTS accuracy_note TEXT;
