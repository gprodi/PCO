-- Base relationnelle existante (structure inspirée des fichiers publics d'IMDb, données d'exemple).
CREATE TABLE title_basics (
    tconst TEXT PRIMARY KEY,
    primaryTitle TEXT NOT NULL,
    startYear INTEGER,
    genres TEXT
);
CREATE TABLE title_ratings (
    tconst TEXT PRIMARY KEY REFERENCES title_basics (tconst),
    averageRating REAL,
    numVotes INTEGER
);
INSERT INTO title_basics VALUES
    ('tt0013442', 'Nosferatu', 1922, 'Fantasy,Horror'),
    ('tt0010323', 'Le Cabinet du docteur Caligari', 1920, 'Horror,Mystery,Thriller'),
    ('tt0000001', 'Dracula', 1897, 'Horror'),
    ('tt0000002', 'L''étrange cas du Dr Jekyll et de Mr Hyde', 1886, 'Horror'),
    ('tt0000003', 'Un film d''horreur confidentiel', 1925, 'Horror'),
    ('tt0000004', 'Le Tour du monde en quatre-vingts jours', 1873, 'Adventure');
INSERT INTO title_ratings VALUES
    ('tt0013442', 7.8, 112000),
    ('tt0010323', 8.0, 70000),
    ('tt0000001', 7.5, 5000),
    ('tt0000002', 7.9, 3000),
    ('tt0000003', 6.0, 40),
    ('tt0000004', 7.2, 9000);
