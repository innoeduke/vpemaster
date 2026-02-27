// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract LevelTracker {
    // Event emitted when a level hash is recorded or revoked
    event LevelRecorded(bytes32 indexed completionHash, string user, uint256 issueDate, uint256 timestamp);
    event LevelRevoked(bytes32 indexed completionHash, string user, uint256 issueDate, uint256 timestamp);

    // Function to record the hash of a level completion
    function recordLevel(bytes32 _hash, string memory _user, uint256 _issueDate) public {
        emit LevelRecorded(_hash, _user, _issueDate, block.timestamp);
    }

    // Function to revoke a previously recorded level completion
    function revokeLevel(bytes32 _hash, string memory _user, uint256 _issueDate) public {
        emit LevelRevoked(_hash, _user, _issueDate, block.timestamp);
    }
}
