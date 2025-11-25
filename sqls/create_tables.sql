CREATE TABLE Contacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Name VARCHAR(100) NOT NULL,
    Club VARCHAR(100),
    Date_Created DATE,
    Current_Project VARCHAR(100),
    Completed_Levels VARCHAR(255)
);

CREATE TABLE Speech_Logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Meeting_Number INT NOT NULL,
    Meeting_Date DATE NOT NULL,
    Session VARCHAR(50) NOT NULL,
    Speech_Title VARCHAR(255),
    Pathway VARCHAR(100),
    Level VARCHAR(50),
    Name VARCHAR(100) NOT NULL,
    Evaluator VARCHAR(100),
    Project_Title VARCHAR(255),
    Project_Type INT,
    Project_Status VARCHAR(50),

    -- Optional indexes for better performance on common queries
    INDEX idx_meeting_date (Meeting_Date),
    INDEX idx_name (Name),
    INDEX idx_pathway (Pathway),
    INDEX idx_level (Level)
);

CREATE TABLE Users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Account VARCHAR(50) NOT NULL,
    Name VARCHAR(255),
    Display_Name VARCHAR(255),
    Date_Created DATE,
    Role VARCHAR(255) NOT NULL
);


CREATE TABLE Projects (
    ID INT PRIMARY KEY,
    Project_Name VARCHAR(255),
    Format VARCHAR(50),
    Duration_Min INT,
    Duration_Max INT,
    Introduction VARCHAR(1000),
    Overview VARCHAR(1000),
    Purpose VARCHAR(255),
    Requirements VARCHAR(500),
    Resources VARCHAR(500),
    Code_DL VARCHAR(5),
    Code_EH VARCHAR(5),
    Code_MS VARCHAR(5),
    Code_PI VARCHAR(5),
    Code_PM VARCHAR(5),
    Code_VC VARCHAR(5)
);

CREATE TABLE `Meetings` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `Meeting_Number` smallint unsigned DEFAULT NULL,
  `Meeting_Date` date DEFAULT NULL,
  `Meeting_Template` varchar(100) DEFAULT NULL,
  `WOD` varchar(100) DEFAULT NULL,
  `best_table_topic_id` int DEFAULT NULL,
  `best_evaluator_id` int DEFAULT NULL,
  `best_speaker_id` int DEFAULT NULL,
  `best_role_taker_id` int DEFAULT NULL,
  PRIMARY KEY (`ID`),
  KEY `fk_best_tt` (`best_table_topic_id`),
  KEY `fk_best_evaluator` (`best_evaluator_id`),
  KEY `fk_best_speaker` (`best_speaker_id`),
  KEY `fk_best_roletaker` (`best_role_taker_id`),
  KEY `idx_meeting_number` (`Meeting_Number`),
  CONSTRAINT `fk_best_evaluator` FOREIGN KEY (`best_evaluator_id`) REFERENCES `Contacts` (`id`),
  CONSTRAINT `fk_best_roletaker` FOREIGN KEY (`best_role_taker_id`) REFERENCES `Contacts` (`id`),
  CONSTRAINT `fk_best_speaker` FOREIGN KEY (`best_speaker_id`) REFERENCES `Contacts` (`id`),
  CONSTRAINT `fk_best_tt` FOREIGN KEY (`best_table_topic_id`) REFERENCES `Contacts` (`id`)
)


CREATE TABLE `Session_Types` (
  `id` int NOT NULL AUTO_INCREMENT,
  `Title` varchar(255) DEFAULT NULL,
  `Default_Owner` varchar(255) DEFAULT NULL,
  `Duration_Min` int DEFAULT NULL,
  `Duration_Max` int DEFAULT NULL,
  `Is_Section` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`id`)
)


CREATE TABLE `Session_Logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `Meeting_Number` smallint unsigned DEFAULT NULL,
  `Type_ID` int DEFAULT NULL,
  `Owner_ID` int DEFAULT NULL,
  `Start_Time` time DEFAULT NULL,
  `Duration_Min` int DEFAULT NULL,
  `Duration_Max` int DEFAULT NULL,
  `Meeting_Seq` int DEFAULT NULL,
  `Notes` varchar(1000) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `Meeting_Number` (`Meeting_Number`),
  KEY `Owner_ID` (`Owner_ID`),
  KEY `Type_ID` (`Type_ID`),
  CONSTRAINT `Session_Logs_ibfk_1` FOREIGN KEY (`Meeting_Number`) REFERENCES `Meetings` (`Meeting_Number`),
  CONSTRAINT `Session_Logs_ibfk_2` FOREIGN KEY (`Owner_ID`) REFERENCES `Contacts` (`id`),
  CONSTRAINT `Session_Logs_ibfk_3` FOREIGN KEY (`Type_ID`) REFERENCES `Session_Types` (`id`)
)

