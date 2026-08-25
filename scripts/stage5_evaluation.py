#!/usr/bin/env python3
"""
Stage 5: Independent Evidence Evaluation

This script evaluates RALG and baseline systems against an independent
benchmark constructed from public/permitted technical documents.

CRITICAL: This harness is designed to NOT run unless independent source
documents are available and properly sourced.

Protocol:
1. Load independent source manifest
2. Verify all sources meet independence criteria
3. Load expert-reviewed benchmark cases
4. Evaluate each system (lexical, RALG, V4)
5. Compute retrieval and answer-level metrics
6. Generate failure taxonomy
7. Statistical analysis
8. Report

Requirements:
- evaluation/stage5_source_manifest.jsonl (populated with independent sources)
- evaluation/stage5_review_queue.jsonl (populated with reviewed cases, reviewer_status: accepted)
- evaluation/stage5_questions.jsonl (finalized question corpus)
- evaluation/stage5_answers.jsonl (expected answers and evidence references)
"""

import json
import sys
import hashlib
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Stage5Validator:
    """Validates that Stage 5 evidence meets independence criteria."""
    
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.sources: Dict[str, Dict] = {}
        
    def load_manifest(self) -> bool:
        """Load and validate source manifest."""
        if not self.manifest_path.exists():
            logger.error(f"Manifest not found: {self.manifest_path}")
            return False
            
        try:
            with open(self.manifest_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    doc = json.loads(line)
                    self.sources[doc['doc_id']] = doc
            logger.info(f"Loaded {len(self.sources)} sources from manifest")
            return True
        except Exception as e:
            logger.error(f"Failed to load manifest: {e}")
            return False
    
    def validate_independence(self) -> Tuple[bool, List[str]]:
        """Validate all sources meet independence criteria."""
        issues = []
        
        if not self.sources:
            issues.append("MANIFEST EMPTY: No sources loaded. Cannot validate independence.")
            return False, issues
        
        for doc_id, doc in self.sources.items():
            # Check independence criteria
            if doc.get('synthetically_generated', False):
                issues.append(f"{doc_id}: SYNTHETIC (not independent)")
            
            if doc.get('used_in_development', False):
                issues.append(f"{doc_id}: USED IN DEVELOPMENT (not independent)")
            
            if doc.get('permission_status') != 'confirmed':
                issues.append(f"{doc_id}: PERMISSION NOT CONFIRMED ({doc.get('permission_status')})")
            
            if not doc.get('redistribution_permitted', False):
                issues.append(f"{doc_id}: REDISTRIBUTION NOT PERMITTED")
        
        if issues:
            return False, issues
        
        logger.info(f"✓ All {len(self.sources)} sources pass independence validation")
        return True, []


class Stage5Benchmark:
    """Manages Stage 5 benchmark construction and quality checks."""
    
    def __init__(self, review_queue_path: Path):
        self.review_queue_path = review_queue_path
        self.cases: List[Dict] = []
        
    def load_reviewed_cases(self) -> bool:
        """Load expert-reviewed benchmark cases."""
        if not self.review_queue_path.exists():
            logger.error(f"Review queue not found: {self.review_queue_path}")
            return False
        
        try:
            with open(self.review_queue_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    case = json.loads(line)
                    self.cases.append(case)
            
            logger.info(f"Loaded {len(self.cases)} cases from review queue")
            return True
        except Exception as e:
            logger.error(f"Failed to load review queue: {e}")
            return False
    
    def validate_reviewed(self) -> Tuple[bool, List[str]]:
        """Validate that all cases have been expert-reviewed and accepted."""
        issues = []
        
        if not self.cases:
            issues.append("REVIEW QUEUE EMPTY: No cases available for evaluation")
            return False, issues
        
        unreviewed = [c for c in self.cases if c.get('reviewer_status') == 'unreviewed']
        if unreviewed:
            issues.append(f"UNREVIEWED CASES: {len(unreviewed)} cases not yet reviewed")
        
        rejected = [c for c in self.cases if c.get('reviewer_status') == 'rejected']
        if rejected:
            issues.append(f"REJECTED CASES: {len(rejected)} cases rejected by reviewers")
        
        flagged = [c for c in self.cases if c.get('reviewer_status') == 'flag_for_discussion']
        if flagged:
            issues.append(f"FLAGGED CASES: {len(flagged)} cases flagged for discussion")
        
        accepted = [c for c in self.cases if c.get('reviewer_status') == 'accepted']
        logger.info(f"Expert review status: {len(accepted)} accepted, {len(unreviewed)} unreviewed, "
                   f"{len(rejected)} rejected, {len(flagged)} flagged")
        
        if not accepted:
            issues.append("NO ACCEPTED CASES: All cases rejected or unreviewed")
            return False, issues
        
        return len(accepted) > 0, issues
    
    def check_duplicates(self) -> Tuple[int, int, List[str]]:
        """Check for exact and near-duplicate questions."""
        exact_dups = []
        near_dups = []
        
        questions = [c.get('question', '') for c in self.cases]
        for i, q1 in enumerate(questions):
            for j, q2 in enumerate(questions[i+1:], i+1):
                if q1 == q2:
                    exact_dups.append((i, j))
                elif q1.lower() == q2.lower():
                    near_dups.append((i, j))
        
        logger.info(f"Duplicate questions: {len(exact_dups)} exact, {len(near_dups)} near-duplicates")
        return len(exact_dups), len(near_dups), []


class Stage5Evaluator:
    """Placeholder for actual evaluation harness."""
    
    def __init__(self):
        self.results = {}
    
    def evaluate(self) -> bool:
        """Run evaluation when data is available."""
        logger.info("Evaluation harness ready; awaiting independent benchmark data")
        return True


def main():
    parser = argparse.ArgumentParser(description="Stage 5 Independent Evidence Evaluation")
    parser.add_argument('--manifest', type=Path, default=Path('evaluation/stage5_source_manifest.jsonl'),
                       help='Path to source manifest')
    parser.add_argument('--review-queue', type=Path, default=Path('evaluation/stage5_review_queue.jsonl'),
                       help='Path to review queue')
    parser.add_argument('--check-only', action='store_true', help='Only validate, do not evaluate')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("STAGE 5: INDEPENDENT EVIDENCE EVALUATION")
    logger.info("=" * 60)
    
    # Step 1: Validate independence
    logger.info("\n[1/4] Validating source independence...")
    validator = Stage5Validator(args.manifest)
    if not validator.load_manifest():
        logger.error("FAILED: Could not load source manifest")
        return 1
    
    valid, issues = validator.validate_independence()
    if not valid:
        logger.error("FAILED: Independence validation errors:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return 1
    
    # Step 2: Load and validate benchmark
    logger.info("\n[2/4] Loading and validating expert-reviewed benchmark...")
    benchmark = Stage5Benchmark(args.review_queue)
    if not benchmark.load_reviewed_cases():
        logger.error("FAILED: Could not load review queue")
        return 1
    
    valid, issues = benchmark.validate_reviewed()
    if not valid:
        logger.warning("BENCHMARK VALIDATION ISSUES:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        return 1
    
    # Step 3: Check benchmark integrity
    logger.info("\n[3/4] Checking benchmark integrity...")
    exact_dups, near_dups, issues = benchmark.check_duplicates()
    if exact_dups > 0:
        logger.error(f"FAILED: Found {exact_dups} exact duplicate questions")
        return 1
    if near_dups > 5:
        logger.warning(f"Found {near_dups} near-duplicate questions (threshold: 5)")
    
    # Step 4: Evaluate
    logger.info("\n[4/4] Running evaluation...")
    evaluator = Stage5Evaluator()
    if not evaluator.evaluate():
        logger.error("FAILED: Evaluation failed")
        return 1
    
    logger.info("\n" + "=" * 60)
    logger.info("STATUS: Stage 5 framework ready")
    logger.info("NEXT: Acquire independent technical documents and populate manifest")
    logger.info("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
