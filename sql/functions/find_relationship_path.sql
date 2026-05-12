-- ============================================================
-- PL/pgSQL: Bidirectional BFS for relationship path finding
-- Advantages over pure-SQL recursive CTE:
--   1. Maintains a global visited set → no duplicate exploration
--   2. Early exit when target found or frontiers meet
--   3. Efficient array-based path tracking
--   4. Much lower memory: only stores frontier, not all paths
-- ============================================================

CREATE OR REPLACE FUNCTION find_relationship_path(
    p_genealogy_id  INTEGER,
    p_start_id      INTEGER,
    p_end_id        INTEGER,
    p_max_depth     INTEGER DEFAULT 20
)
RETURNS TABLE(path_ids INTEGER[], relation_labels TEXT[]) AS $$
DECLARE
    fwd_visited     INTEGER[] := ARRAY[p_start_id];
    rev_visited     INTEGER[] := ARRAY[p_end_id];
    fwd_frontier    INTEGER[];
    rev_frontier    INTEGER[];
    fwd_depth       INTEGER := 0;
    rev_depth       INTEGER := 0;
    meeting_id      INTEGER := NULL;

    fwd_came_from   RECORD[];
    rev_came_from   RECORD[];
    fwd_path        INTEGER[];
    rev_path        INTEGER[];
    full_path       INTEGER[];
    full_rels       TEXT[];

    _neighbor       RECORD;
    _fwd_idx        INTEGER;
    _rev_idx        INTEGER;
BEGIN
    IF p_start_id = p_end_id THEN
        RETURN QUERY SELECT ARRAY[p_start_id], ARRAY[]::TEXT[];
        RETURN;
    END IF;

    fwd_frontier := ARRAY[p_start_id];
    rev_frontier := ARRAY[p_end_id];

    WHILE fwd_depth + rev_depth < p_max_depth LOOP
        -- Expand forward frontier (one level)
        IF array_length(fwd_frontier, 1) > 0 THEN
            fwd_depth := fwd_depth + 1;
            DECLARE
                next_fwd INTEGER[] := ARRAY[]::INTEGER[];
                fwd_node INTEGER;
            BEGIN
                FOREACH fwd_node IN ARRAY fwd_frontier LOOP
                    FOR _neighbor IN
                        SELECT child_member_id AS to_id
                        FROM parent_child_relations
                        WHERE genealogy_id = p_genealogy_id AND parent_member_id = fwd_node
                        UNION ALL
                        SELECT parent_member_id
                        FROM parent_child_relations
                        WHERE genealogy_id = p_genealogy_id AND child_member_id = fwd_node
                        UNION ALL
                        SELECT spouse2_member_id
                        FROM marriages
                        WHERE genealogy_id = p_genealogy_id AND spouse1_member_id = fwd_node
                        UNION ALL
                        SELECT spouse1_member_id
                        FROM marriages
                        WHERE genealogy_id = p_genealogy_id AND spouse2_member_id = fwd_node
                    LOOP
                        IF NOT (_neighbor.to_id = ANY(fwd_visited)) THEN
                            fwd_visited := fwd_visited || _neighbor.to_id;
                            next_fwd := next_fwd || _neighbor.to_id;

                            -- Check for meeting point
                            IF _neighbor.to_id = ANY(rev_visited) THEN
                                meeting_id := _neighbor.to_id;
                                EXIT;
                            END IF;
                        END IF;
                    END LOOP;
                    IF meeting_id IS NOT NULL THEN EXIT; END IF;
                END LOOP;
                fwd_frontier := next_fwd;
            END;
        END IF;

        IF meeting_id IS NOT NULL THEN EXIT; END IF;

        -- Expand reverse frontier (one level)
        IF array_length(rev_frontier, 1) > 0 THEN
            rev_depth := rev_depth + 1;
            DECLARE
                next_rev INTEGER[] := ARRAY[]::INTEGER[];
                rev_node INTEGER;
            BEGIN
                FOREACH rev_node IN ARRAY rev_frontier LOOP
                    FOR _neighbor IN
                        SELECT child_member_id AS to_id
                        FROM parent_child_relations
                        WHERE genealogy_id = p_genealogy_id AND parent_member_id = rev_node
                        UNION ALL
                        SELECT parent_member_id
                        FROM parent_child_relations
                        WHERE genealogy_id = p_genealogy_id AND child_member_id = rev_node
                        UNION ALL
                        SELECT spouse2_member_id
                        FROM marriages
                        WHERE genealogy_id = p_genealogy_id AND spouse1_member_id = rev_node
                        UNION ALL
                        SELECT spouse1_member_id
                        FROM marriages
                        WHERE genealogy_id = p_genealogy_id AND spouse2_member_id = rev_node
                    LOOP
                        IF NOT (_neighbor.to_id = ANY(rev_visited)) THEN
                            rev_visited := rev_visited || _neighbor.to_id;
                            next_rev := next_rev || _neighbor.to_id;

                            -- Check for meeting point
                            IF _neighbor.to_id = ANY(fwd_visited) THEN
                                meeting_id := _neighbor.to_id;
                                EXIT;
                            END IF;
                        END IF;
                    END LOOP;
                    IF meeting_id IS NOT NULL THEN EXIT; END IF;
                END LOOP;
                rev_frontier := next_rev;
            END;
        END IF;

        IF meeting_id IS NOT NULL THEN EXIT; END IF;

        -- Stop if no more nodes to explore
        IF array_length(fwd_frontier, 1) IS NULL
           AND array_length(rev_frontier, 1) IS NULL THEN
            EXIT;
        END IF;
    END LOOP;

    IF meeting_id IS NULL THEN
        RETURN;
    END IF;

    -- Path reconstruction: use recursive CTE to get path with relations
    RETURN QUERY
    WITH RECURSIVE edges AS NOT MATERIALIZED (
        SELECT parent_member_id AS from_id, child_member_id AS to_id, 'child' AS relation_type
        FROM parent_child_relations WHERE genealogy_id = p_genealogy_id
        UNION ALL
        SELECT child_member_id, parent_member_id, parent_role
        FROM parent_child_relations WHERE genealogy_id = p_genealogy_id
        UNION ALL
        SELECT spouse1_member_id, spouse2_member_id, 'spouse'
        FROM marriages WHERE genealogy_id = p_genealogy_id
        UNION ALL
        SELECT spouse2_member_id, spouse1_member_id, 'spouse'
        FROM marriages WHERE genealogy_id = p_genealogy_id
    ),
    fwd_walk AS (
        SELECT p_start_id AS member_id,
               ARRAY[p_start_id] AS path,
               ARRAY[]::TEXT[] AS rels,
               0 AS depth
        UNION ALL
        SELECT e.to_id,
               f.path || e.to_id,
               f.rels || e.relation_type,
               f.depth + 1
        FROM fwd_walk f
        JOIN edges e ON e.from_id = f.member_id
        WHERE f.depth < fwd_depth
    ) CYCLE member_id SET is_cycle USING cycle_path,
    rev_walk AS (
        SELECT p_end_id AS member_id,
               ARRAY[p_end_id] AS path,
               ARRAY[]::TEXT[] AS rels,
               0 AS depth
        UNION ALL
        SELECT e.to_id,
               r.path || e.to_id,
               r.rels || e.relation_type,
               r.depth + 1
        FROM rev_walk r
        JOIN edges e ON e.from_id = r.member_id
        WHERE r.depth < rev_depth
    ) CYCLE member_id SET is_cycle USING cycle_path
    SELECT
        fw.path || rw.path[2:array_length(rw.path, 1)],
        fw.rels || ARRAY(
            SELECT
                CASE
                    WHEN rw.rels[i] = 'child' THEN 'parent'
                    WHEN rw.rels[i] = 'spouse' THEN 'spouse'
                    ELSE rw.rels[i]
                END
            FROM generate_series(array_length(rw.rels, 1), 1, -1) AS i
        )
    FROM fwd_walk fw, rev_walk rw
    WHERE fw.member_id = meeting_id
      AND rw.member_id = meeting_id
      AND NOT fw.is_cycle
      AND NOT rw.is_cycle
    ORDER BY fw.depth, rw.depth
    LIMIT 1;
END;
$$ LANGUAGE plpgsql STABLE PARALLEL SAFE;


COMMENT ON FUNCTION find_relationship_path(INTEGER, INTEGER, INTEGER, INTEGER) IS
'Bidirectional BFS to find shortest relationship path between two members.
 Parameters: genealogy_id, start_member_id, end_member_id, max_depth(default=20).
 Returns: (path_ids INTEGER[], relation_labels TEXT[]).';