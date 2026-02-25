// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract LevelTracker {
    // Event emitted when a level hash is recorded
    event LevelRecorded(bytes32 indexed completionHash, uint256 timestamp);

    // Function to record the hash of a level completion
    function recordLevel(bytes32 _hash) public {
        emit LevelRecorded(_hash, block.timestamp);
    }
}
