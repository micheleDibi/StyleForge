-- ============================================
-- STEP 7: Dati iniziali (ruoli, permessi, lookup data)
-- ============================================

-- Ruoli
INSERT INTO roles (name, description, is_default) VALUES
('admin', 'Amministratore con accesso completo e crediti infiniti', FALSE),
('user', 'Utente standard con accesso limitato', TRUE);

-- Permessi admin: tutti
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r, (VALUES ('train'), ('generate'), ('humanize'), ('thesis'), ('detect'), ('manage_templates')) AS p(code)
WHERE r.name = 'admin';

-- Permessi user: solo train e thesis
INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r, (VALUES ('train'), ('thesis')) AS p(code)
WHERE r.name = 'user';

-- Writing styles
INSERT INTO writing_styles (code, name, description, prompt_hint, sort_order) VALUES
('academic', 'Accademico', 'Stile formale e rigoroso per tesi e paper', 'Usa linguaggio formale, cita fonti, mantieni rigore metodologico', 1),
('professional', 'Professionale', 'Chiaro e diretto per report aziendali', 'Tono professionale accessibile, focus su chiarezza e praticità', 2),
('technical', 'Tecnico', 'Preciso con terminologia specialistica', 'Terminologia tecnica, dettagli implementativi, precisione', 3),
('journalistic', 'Giornalistico', 'Coinvolgente e narrativo', 'Stile narrativo, esempi concreti, mantieni interesse', 4),
('educational', 'Didattico', 'Chiaro e pedagogico', 'Spiega in modo progressivo, usa esempi, anticipa domande', 5),
('creative', 'Creativo', 'Espressivo e originale', 'Metafore, analogie, originalità mantenendo chiarezza', 6);

-- Content depth levels
INSERT INTO content_depth_levels (code, name, description, detail_multiplier, sort_order) VALUES
('overview', 'Panoramica', 'Trattazione generale', 0.7, 1),
('intermediate', 'Intermedio', 'Livello bilanciato', 1.0, 2),
('detailed', 'Dettagliato', 'Approfondimento con analisi estese', 1.3, 3),
('expert', 'Esperto', 'Massimo dettaglio e complessità', 1.5, 4);

-- Audience knowledge levels
INSERT INTO audience_knowledge_levels (code, name, description, prompt_hint, sort_order) VALUES
('beginner', 'Principiante', 'Nessuna conoscenza pregressa', 'Spiega concetti base, evita jargon, usa analogie', 1),
('intermediate', 'Intermedio', 'Conoscenze di base', 'Assumi conoscenze fondamentali, spiega concetti avanzati', 2),
('advanced', 'Avanzato', 'Buona preparazione', 'Terminologia tecnica, focus su aspetti avanzati', 3),
('expert', 'Esperto', 'Specialisti del settore', 'Linguaggio specialistico, aspetti tecnici complessi', 4);

-- Audience sizes
INSERT INTO audience_sizes (code, name, description, sort_order) VALUES
('individual', 'Individuale', 'Singolo destinatario', 1),
('small_group', 'Piccolo Gruppo', 'Team 5-20 persone', 2),
('medium', 'Medio', 'Dipartimento 20-100 persone', 3),
('large', 'Ampio', 'Organizzazione 100+ persone', 4);

-- Industries
INSERT INTO industries (code, name, description, keywords, sort_order) VALUES
('technology', 'Tecnologia', 'IT, software, digitale', ARRAY['software', 'IT', 'digitale'], 1),
('healthcare', 'Sanità', 'Medicina, farmaceutica', ARRAY['medicina', 'salute'], 2),
('finance', 'Finanza', 'Banche, investimenti', ARRAY['banca', 'investimenti'], 3),
('education', 'Istruzione', 'Scuole, università', ARRAY['scuola', 'università'], 4),
('engineering', 'Ingegneria', 'Meccanica, civile', ARRAY['ingegneria', 'costruzioni'], 5),
('law', 'Giurisprudenza', 'Legale, normativo', ARRAY['legge', 'diritto'], 6),
('marketing', 'Marketing', 'Comunicazione, pubblicità', ARRAY['marketing', 'brand'], 7),
('science', 'Scienze', 'Ricerca scientifica', ARRAY['ricerca', 'scienza'], 8),
('humanities', 'Scienze Umane', 'Filosofia, storia, arte', ARRAY['filosofia', 'storia'], 9),
('business', 'Business', 'Management, strategia', ARRAY['management', 'strategia'], 10),
('environment', 'Ambiente', 'Ecologia, sostenibilità', ARRAY['ambiente', 'green'], 11),
('other', 'Altro', 'Altri settori', ARRAY[]::TEXT[], 99);

-- Target audiences
INSERT INTO target_audiences (code, name, description, prompt_hint, sort_order) VALUES
('thesis_committee', 'Commissione di Laurea', 'Professori e relatori', 'Rigore accademico, padronanza metodologica', 1),
('professors', 'Docenti', 'Professori e ricercatori', 'Linguaggio accademico, aspetti teorici', 2),
('students', 'Studenti', 'Studenti universitari', 'Bilancia teoria e pratica, esempi concreti', 3),
('executives', 'Dirigenti', 'Manager e C-level', 'Implicazioni strategiche, concisione', 4),
('technical_team', 'Team Tecnico', 'Sviluppatori, ingegneri', 'Dettagli implementativi, terminologia tecnica', 5),
('general_public', 'Pubblico Generale', 'Lettori non specializzati', 'Evita jargon, usa esempi quotidiani', 6),
('investors', 'Investitori', 'Venture capital', 'Opportunità, mercato, scalabilità', 7),
('clients', 'Clienti', 'Clienti aziendali', 'Benefici e valore, linguaggio accessibile', 8);
