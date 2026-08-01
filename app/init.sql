CREATE TABLE IF NOT EXISTS employee (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL
);

DO $$ BEGIN
    CREATE TYPE attendance_status AS ENUM ('Present', 'Sick', 'Leave', 'Absent');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS attendance (
    id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES employee(id) ON DELETE CASCADE,
    employee_name VARCHAR(50) NOT NULL,
    attendance_date DATE NOT NULL DEFAULT CURRENT_DATE,
    check_in TIME NULL,
    check_out TIME NULL,
    status attendance_status NOT NULL,
    notes VARCHAR(255) NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NULL,
    deleted_at TIMESTAMP WITH TIME ZONE NULL,

    CONSTRAINT chk_check_out_after_check_in CHECK (check_out IS NULL OR check_out >= check_in),

    CONSTRAINT chk_present_requires_check_in CHECK (status != 'Present' OR check_in IS NOT NULL),

    CONSTRAINT unique_employee_daily_attendance UNIQUE (employee_id, attendance_date)
);

INSERT INTO employee (id, name) VALUES 
    (1, 'John Doe'),
    (2, 'Jane Smith'),
    (3, 'Alice Johnson'),
    (4, 'Bob Williams'),
    (5, 'Charlie Brown')
ON CONFLICT (id) DO NOTHING;

SELECT setval('employee_id_seq', (SELECT MAX(id) FROM employee));

INSERT INTO attendance (employee_id, employee_name, attendance_date, check_in, check_out, status, notes) VALUES
    (1, 'John Doe', '2026-07-01', '07:30:00', '16:00:00', 'Present', 'Hadir tepat waktu'),
    (2, 'Jane Smith', '2026-07-01', '08:00:00', '17:00:00', 'Present', NULL),
    (3, 'Alice Johnson', '2026-07-01', NULL, NULL, 'Sick', 'Demam tinggi'),
    (4, 'Bob Williams', '2026-07-01', NULL, NULL, 'Leave', 'Cuti tahunan'),
    (5, 'Charlie Brown', '2026-07-01', NULL, NULL, 'Absent', 'Tanpa keterangan'),
    (1, 'John Doe', '2026-07-02', '07:45:00', '16:30:00', 'Present', NULL),
    (2, 'Jane Smith', '2026-07-02', '07:50:00', '16:45:00', 'Present', NULL),
    (3, 'Alice Johnson', '2026-07-02', '08:15:00', '17:00:00', 'Present', 'Izin terlambat'),
    (4, 'Bob Williams', '2026-07-02', NULL, NULL, 'Leave', 'Cuti tahunan'),
    (5, 'Charlie Brown', '2026-07-02', '08:00:00', '17:00:00', 'Present', NULL)
ON CONFLICT DO NOTHING;

SELECT setval('attendance_id_seq', (SELECT MAX(id) FROM attendance));